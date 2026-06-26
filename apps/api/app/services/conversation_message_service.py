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
            detail="sender_user_id is not an active member of this workspace.",
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
            detail="Agent not found.",
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
                detail="current_user_id is required for sender_type='human'.",
            )
        uid = data.sender_user_id if data.sender_user_id is not None else current_user_id
        _require_active_member(db, workspace_id, uid)
        sender_user_id = uid

    elif data.sender_type == "customer":
        if data.sender_user_id is not None:
            # Customer messages don't carry an internal user.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="sender_user_id must not be set for sender_type='customer'.",
            )

    elif data.sender_type == "agent":
        # Use explicit agent_id, fall back to conversation's agent, error if neither.
        aid = data.agent_id if data.agent_id is not None else conv.agent_id
        if aid is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "agent_id is required for sender_type='agent' "
                    "when the conversation has no assigned agent."
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

    # Update conversation timestamps.
    now = datetime.now(timezone.utc)
    conv.last_message_at = msg.created_at or now
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
            from app.services.conversation_agent_reply_service import (  # noqa: PLC0415
                generate_conversation_agent_reply,
            )
            generate_conversation_agent_reply(db, workspace_id, conv, msg)
        except Exception:
            # Reply service must never crash the message creation endpoint.
            logger.exception(
                "Auto-reply failed for conversation %s message %s",
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
            from app.services.whatsapp_outbound_service import (  # noqa: PLC0415
                deliver_human_message,
            )
            deliver_human_message(db, msg, conv)
        except Exception:
            logger.exception(
                "WhatsApp delivery failed for conversation %s message %s",
                conv.id,
                msg.id,
            )

    return msg
