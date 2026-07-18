import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberStatus
from app.models.agent import Agent
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.workspace_member import WorkspaceMember
from app.schemas.conversation_message import ConversationMessageCreate
from app.services.conversation_service import get_conversation_or_404

logger = logging.getLogger(__name__)

_MAX_LIMIT = 200
_AUTO_REPLY_ALLOWED_STATUSES = {"open", "pending"}


def should_auto_reply_to_message(
    conversation: Conversation,
    message: ConversationMessage,
) -> tuple[bool, str | None]:
    """
    Pure eligibility check: should the auto-reply service be called for *message*?

    Returns (True, None) when the service should be invoked.
    Returns (False, reason_code) when it should be skipped.

    This check mirrors the early-exit conditions inside
    generate_conversation_agent_reply, but runs before any DB query so that
    obviously ineligible messages never touch the reply service at all.
    """
    if message.direction != "inbound" or message.sender_type != "customer":
        return False, "not_customer_inbound"
    if not conversation.ai_enabled:
        return False, "ai_disabled"
    if conversation.agent_id is None:
        return False, "no_agent"
    if conversation.status not in _AUTO_REPLY_ALLOWED_STATUSES:
        return False, "status_not_allowed"
    if conversation.assigned_user_id is not None:
        return False, "human_assigned"
    return True, None


def list_messages(
    db: Session,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> list[ConversationMessage]:
    # Ensure conversation belongs to workspace (raises 404 if not).
    get_conversation_or_404(db, workspace_id, conversation_id)

    effective_limit = min(limit, _MAX_LIMIT)
    return list(
        db.scalars(
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.workspace_id == workspace_id,
            )
            .order_by(ConversationMessage.created_at.asc())
            .offset(skip)
            .limit(effective_limit)
        ).all()
    )


def _require_active_member(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == MemberStatus.active,
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="sender_user_id não corresponde a um membro ativo deste workspace.",
        )


def _require_agent(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado.",
        )
    return agent


def create_message(
    db: Session,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    current_user_id: uuid.UUID | None,
    data: ConversationMessageCreate,
) -> ConversationMessage:
    conv: Conversation = get_conversation_or_404(db, workspace_id, conversation_id)

    sender_user_id: uuid.UUID | None = None
    resolved_agent_id: uuid.UUID | None = None

    if data.sender_type == "human":
        # Default to the authenticated user if not specified.
        # current_user_id must be present for human messages (public widget passes None).
        if current_user_id is None and data.sender_user_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="current_user_id é obrigatório quando sender_type='human'.",
            )
        uid = data.sender_user_id if data.sender_user_id is not None else current_user_id
        _require_active_member(db, workspace_id, uid)
        sender_user_id = uid

    elif data.sender_type == "customer":
        if data.sender_user_id is not None:
            # Customer messages don't carry an internal user.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="sender_user_id não deve ser informado quando sender_type='customer'.",
            )

    elif data.sender_type == "agent":
        # Use explicit agent_id, fall back to conversation's agent, error if neither.
        aid = data.agent_id if data.agent_id is not None else conv.agent_id
        if aid is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "agent_id é obrigatório quando sender_type='agent' "
                    "e a conversa não possui um agente atribuído."
                ),
            )
        _require_agent(db, workspace_id, aid)
        resolved_agent_id = aid

    elif data.sender_type == "system":
        pass  # No sender_user_id or agent_id needed.

    # For non-agent senders, a manually supplied agent_id is still validated if present.
    if data.sender_type != "agent" and data.agent_id is not None:
        _require_agent(db, workspace_id, data.agent_id)
        resolved_agent_id = data.agent_id

    msg = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        direction=data.direction,
        sender_type=data.sender_type,
        sender_user_id=sender_user_id,
        agent_id=resolved_agent_id,
        content=data.content,
        content_type=data.content_type,
        metadata_json=data.metadata,
    )
    db.add(msg)
    db.flush()  # Assign id and created_at from the DB.

    # Auto-reopen: a conversation the "mark_resolved" tool (or a human) closed
    # shouldn't stay permanently silent just because the customer wrote again
    # — see mark-resolved-tool-prd.md. WhatsApp doesn't hit this path for a
    # resolved conversation (its own lookup only matches open/pending, so it
    # spins up a new conversation instead) — this only matters here, for the
    # widget/API path, which reuses one persistent conversation per session.
    if data.sender_type == "customer" and conv.status == "resolved":
        conv.status = "open"
        conv.resolution_summary = None

    # Update conversation timestamps.
    now = datetime.now(timezone.utc)
    conv.last_message_at = msg.created_at or now
    if data.sender_type == "customer":
        # Anchor for conversation_follow_up_scheduler.py — see Conversation model
        # docstring for why this must be separate from last_message_at.
        conv.last_customer_message_at = msg.created_at or now
    conv.updated_at = now

    # Commit the customer message before triggering auto-reply so that it is
    # always persisted even if the reply service fails.
    db.commit()
    db.refresh(msg)

    # ── Auto-reply trigger ────────────────────────────────────────────────────
    # Reload conv to pick up the committed state (last_message_at etc.).
    db.refresh(conv)
    eligible, _reason = should_auto_reply_to_message(conv, msg)
    if eligible:
        try:
            from sqlalchemy import select as _select  # noqa: PLC0415

            from app.models.agent_prompt_settings import AgentPromptSettings  # noqa: PLC0415
            from app.services.auto_reply_scheduler import (  # noqa: PLC0415
                schedule_agent_auto_reply,
            )
            prompt_cfg = db.scalar(
                _select(AgentPromptSettings)
                .where(AgentPromptSettings.agent_id == conv.agent_id)
            )
            delay = int(getattr(prompt_cfg, "reply_delay_seconds", 0) or 0)
            schedule_agent_auto_reply(
                workspace_id=workspace_id,
                conversation_id=conv.id,
                agent_id=conv.agent_id,
                trigger_message_id=msg.id,
                delay_seconds=delay,
                db=db,
            )
        except Exception:
            # Scheduler must never crash the message creation endpoint.
            logger.exception(
                "Auto-reply scheduling failed for conversation %s message %s",
                conv.id,
                msg.id,
            )

    # ── WhatsApp outbound delivery ────────────────────────────────────────────
    if (
        msg.direction == "outbound"
        and msg.sender_type == "human"
        and conv.channel_type == "whatsapp"
    ):
        try:
            from app.services.messaging import deliver_outbound_message  # noqa: PLC0415
            deliver_outbound_message(db, msg, conv)
        except Exception:
            logger.exception(
                "WhatsApp delivery failed for conversation %s message %s",
                conv.id,
                msg.id,
            )

    return msg
