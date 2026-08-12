"""
WhatsApp Coexistence processing — whatsapp-coexistence-prd.md.

Handles the three webhook fields specific to a number connected via
Coexistence (Business App + Cloud API on the same number, not the standard
Embedded Signup migration):

- `history`              — past messages shared on connection.
- `smb_app_state_sync`   — contacts added/removed in the owner's WhatsApp.
- `smb_message_echoes`   — messages the owner sends via their own app.

Design notes (mirrors whatsapp_inbound_service.py):
- Never raises — callers (the webhook router) must always return 200 to Meta.
- Writes directly to the ORM models for the same reasons as inbound
  processing: no authenticated user in the webhook context, idempotency by
  external_message_id, direction/sender_type is derived, not user input.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.channel_service import get_whatsapp_channel_by_phone_number_id
from app.services.pipeline_service import ensure_conversation_pipeline_entry
from app.services.whatsapp_webhook_parser import (
    WhatsAppHistoryMessage,
    WhatsAppMessageEcho,
    WhatsAppStateSyncContact,
)

logger = logging.getLogger(__name__)

_ECHO_HANDOFF_REASON = "Dono respondeu pelo WhatsApp Business App"


# ── History sync ─────────────────────────────────────────────────────────────


def process_history_message(db: Session, msg: WhatsAppHistoryMessage) -> None:
    """
    Import one historical message shared on Coexistence connection.

    Never raises. Skips silently if the channel isn't found (e.g. a stray
    webhook for a channel that was later disconnected).
    """
    try:
        _process_history_message(db, msg)
    except Exception:
        logger.exception(
            "whatsapp_coexistence history import failed wamid=%s phone_number_id=%s",
            msg.wamid,
            msg.phone_number_id,
        )


def _process_history_message(db: Session, msg: WhatsAppHistoryMessage) -> None:
    channel = get_whatsapp_channel_by_phone_number_id(db, msg.phone_number_id)
    if channel is None:
        logger.info(
            "whatsapp_coexistence history channel not found phone_number_id=%s wamid=%s",
            msg.phone_number_id,
            msg.wamid,
        )
        return

    workspace_id = channel.workspace_id
    contact = _get_or_create_contact_by_wa_id(db, workspace_id, msg.thread_wa_id, None)
    conversation = _get_or_create_conversation_no_quota(
        db, workspace_id, contact, channel.agent_id, channel.id
    )

    existing = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation.id,
            ConversationMessage.external_message_id == msg.wamid,
        )
    )
    if existing is not None:
        return

    created_at = (
        datetime.fromtimestamp(msg.timestamp, tz=timezone.utc)
        if msg.timestamp
        else datetime.now(timezone.utc)
    )
    sender_type = "human" if msg.direction == "outbound" else "customer"

    message = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction=msg.direction,
        sender_type=sender_type,
        content_type="text",
        content=msg.text_body or "[mensagem vazia — histórico]",
        external_message_id=msg.wamid,
        metadata_json={
            "imported_from": "whatsapp_business_app_history",
            "whatsapp_timestamp": msg.timestamp,
            "history_phase": msg.phase,
            "history_chunk_order": msg.chunk_order,
        },
        created_at=created_at,
    )
    db.add(message)

    if conversation.last_message_at is None or created_at > conversation.last_message_at:
        conversation.last_message_at = created_at
        if msg.direction == "inbound":
            conversation.last_customer_message_at = created_at
    db.commit()

    logger.info(
        "whatsapp_coexistence history message imported wamid=%s conversation=%s "
        "direction=%s phase=%s progress=%s",
        msg.wamid,
        conversation.id,
        msg.direction,
        msg.phase,
        msg.progress,
    )


# ── Contact state sync ─────────────────────────────────────────────────────────


def process_state_sync_contact(db: Session, item: WhatsAppStateSyncContact) -> None:
    """Never raises. `remove` events are logged only — see PRD for why."""
    try:
        _process_state_sync_contact(db, item)
    except Exception:
        logger.exception(
            "whatsapp_coexistence state_sync failed phone_number_id=%s contact_phone=%s",
            item.phone_number_id,
            item.contact_phone,
        )


def _process_state_sync_contact(db: Session, item: WhatsAppStateSyncContact) -> None:
    channel = get_whatsapp_channel_by_phone_number_id(db, item.phone_number_id)
    if channel is None:
        logger.info(
            "whatsapp_coexistence state_sync channel not found phone_number_id=%s",
            item.phone_number_id,
        )
        return

    if item.action == "remove":
        # Deliberately not deleting anything — see "Fora de escopo" in the PRD.
        logger.info(
            "whatsapp_coexistence contact remove event (no-op) phone_number_id=%s contact=%s",
            item.phone_number_id,
            item.contact_phone,
        )
        return

    name = item.full_name or item.first_name
    _get_or_create_contact_by_wa_id(db, channel.workspace_id, item.contact_phone, name)
    db.commit()
    logger.info(
        "whatsapp_coexistence contact synced workspace=%s contact=%s",
        channel.workspace_id,
        item.contact_phone,
    )


# ── Message echoes ──────────────────────────────────────────────────────────────


def process_message_echo(db: Session, echo: WhatsAppMessageEcho) -> None:
    """Never raises."""
    try:
        _process_message_echo(db, echo)
    except Exception:
        logger.exception(
            "whatsapp_coexistence echo processing failed wamid=%s phone_number_id=%s",
            echo.wamid,
            echo.phone_number_id,
        )


def _process_message_echo(db: Session, echo: WhatsAppMessageEcho) -> None:
    channel = get_whatsapp_channel_by_phone_number_id(db, echo.phone_number_id)
    if channel is None:
        logger.info(
            "whatsapp_coexistence echo channel not found phone_number_id=%s wamid=%s",
            echo.phone_number_id,
            echo.wamid,
        )
        return

    workspace_id = channel.workspace_id
    contact = _get_or_create_contact_by_wa_id(db, workspace_id, echo.to_number, None)
    conversation = _get_or_create_conversation_no_quota(
        db, workspace_id, contact, channel.agent_id, channel.id
    )

    existing = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation.id,
            ConversationMessage.external_message_id == echo.wamid,
        )
    )
    if existing is not None:
        return

    now = datetime.now(timezone.utc)
    message = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_type="human",
        sender_user_id=None,
        content_type="text",
        content=echo.text_body or "[mensagem vazia — WhatsApp Business App]",
        external_message_id=echo.wamid,
        metadata_json={
            "source": "whatsapp_business_app_echo",
            "whatsapp_timestamp": echo.timestamp,
        },
    )
    db.add(message)

    conversation.last_message_at = now
    conversation.updated_at = now

    # A human just replied from their own phone — pause the AI the same way
    # a manual "Assumir"/request_human handoff does, so the agent doesn't
    # answer over what the owner just said. Never re-enabled automatically;
    # someone has to turn it back on from the Inbox, same as any other
    # handoff (see PRD).
    if conversation.ai_enabled:
        conversation.ai_enabled = False
        conversation.handoff_reason = _ECHO_HANDOFF_REASON

    db.commit()

    logger.info(
        "whatsapp_coexistence echo recorded wamid=%s conversation=%s ai_paused=%s",
        echo.wamid,
        conversation.id,
        True,
    )


# ── Shared helpers ───────────────────────────────────────────────────────────────


def _get_or_create_contact_by_wa_id(
    db: Session,
    workspace_id: uuid.UUID,
    wa_id: str,
    profile_name: str | None,
) -> Contact:
    external_id = f"whatsapp:{wa_id}"
    contact = db.scalar(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.external_id == external_id,
        )
    )
    if contact is None:
        contact = Contact(
            workspace_id=workspace_id,
            name=profile_name or wa_id,
            phone=f"+{wa_id}",
            external_id=external_id,
            metadata_json={"source": "whatsapp", "whatsapp": {"wa_id": wa_id}},
        )
        db.add(contact)
        db.flush()
    elif profile_name and contact.name == wa_id:
        contact.name = profile_name
        contact.updated_at = datetime.now(timezone.utc)
        db.flush()
    return contact


def _get_or_create_conversation_no_quota(
    db: Session,
    workspace_id: uuid.UUID,
    contact: Contact,
    agent_id: uuid.UUID | None,
    channel_id: uuid.UUID,
) -> Conversation:
    """
    Same lookup as whatsapp_inbound_service._get_or_create_conversation, but
    deliberately does NOT call plan_service.count_new_conversation — history
    imports and echoes reflect conversations that (at least partly) happened
    outside Wenzap, so they shouldn't consume the workspace's "new
    conversation" usage counter. See PRD.
    """
    conversation = db.scalar(
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.contact_id == contact.id,
            Conversation.agent_id == agent_id,
            Conversation.channel_type == "whatsapp",
            Conversation.status.in_(["open", "pending"]),
        )
        .order_by(Conversation.created_at.desc())
    )
    if conversation is not None:
        if conversation.channel_id != channel_id:
            conversation.channel_id = channel_id
            db.flush()
        return conversation

    now = datetime.now(timezone.utc)
    conversation = Conversation(
        workspace_id=workspace_id,
        contact_id=contact.id,
        agent_id=agent_id,
        channel_id=channel_id,
        channel_type="whatsapp",
        status="open",
        ai_enabled=True,
        assigned_user_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.flush()
    ensure_conversation_pipeline_entry(db, conversation)
    return conversation
