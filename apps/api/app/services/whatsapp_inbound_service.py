"""
WhatsApp inbound processing service.

Orchestrates: Channel lookup → Contact upsert → Conversation upsert → Message creation
→ (optional) AI auto-reply.

Design notes:
- Never raises — all exceptions are caught and logged so the webhook endpoint
  always returns 200 to Meta.
- Writes directly to the ORM models instead of going through the public
  create_message() service, because:
    (a) there is no authenticated user in the webhook context;
    (b) we need to persist external_message_id for idempotency;
    (c) ai_enabled follows channel.config_json.auto_reply_enabled, not a fixed default.
- Idempotency: duplicate wamid within the same conversation is detected via
  external_message_id and silently returns the existing message without triggering
  auto-reply a second time.
- Auto-reply: triggered only for new messages when conversation.ai_enabled=True.
  Existing conversations preserve their ai_enabled value so that a human takeover
  is respected across subsequent messages.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.channel_service import get_whatsapp_channel_by_phone_number_id
from app.services.pipeline_service import ensure_conversation_pipeline_entry
from app.services.whatsapp_webhook_parser import WhatsAppInboundMessage

logger = logging.getLogger(__name__)


def process_inbound_message(
    db: Session,
    msg: WhatsAppInboundMessage,
    channel: Channel | None = None,
) -> ConversationMessage | None:
    """
    Process one inbound WhatsApp text message and persist it to the Inbox.

    `channel` may be pre-resolved by the caller (e.g. the Evolution webhook,
    which routes by instance name rather than Meta's phone_number_id). When
    omitted, the channel is looked up by msg.phone_number_id — the original
    Meta Cloud API behavior, unchanged.

    Returns the ConversationMessage (new or existing) on success.
    Returns None if the channel was not found or an unexpected error occurred.
    """
    try:
        return _process(db, msg, channel)
    except Exception:
        logger.exception(
            "whatsapp_inbound unexpected error processing wamid=%s phone_number_id=%s",
            msg.wamid,
            msg.phone_number_id,
        )
        return None


# ── Private orchestration ──────────────────────────────────────────────────────


def _process(
    db: Session, msg: WhatsAppInboundMessage, channel: Channel | None = None
) -> ConversationMessage | None:
    if channel is None:
        channel = get_whatsapp_channel_by_phone_number_id(db, msg.phone_number_id)
    if channel is None:
        logger.info(
            "whatsapp_inbound channel not found for phone_number_id=%s wamid=%s",
            msg.phone_number_id,
            msg.wamid,
        )
        return None

    workspace_id: uuid.UUID = channel.workspace_id
    agent_id: uuid.UUID | None = channel.agent_id
    auto_reply_enabled: bool = bool((channel.config_json or {}).get("auto_reply_enabled", False))

    contact = _get_or_create_contact(db, workspace_id, msg)
    conversation = _get_or_create_conversation(
        db,
        workspace_id,
        contact,
        agent_id,
        channel_id=channel.id,
        auto_reply_enabled=auto_reply_enabled,
    )
    message, is_new = _create_message_idempotent(db, workspace_id, conversation, msg, channel)

    logger.info(
        "whatsapp_auto_reply_check conversation_id=%s ai_enabled=%s agent_id=%s "
        "assigned_user_id=%s status=%s is_new=%s auto_reply_enabled=%s",
        conversation.id,
        conversation.ai_enabled,
        conversation.agent_id,
        conversation.assigned_user_id,
        conversation.status,
        is_new,
        auto_reply_enabled,
    )

    # Only trigger auto-reply for genuinely new messages, never for duplicates.
    if is_new and conversation.ai_enabled:
        logger.info(
            "whatsapp_auto_reply_trigger conversation_id=%s message_id=%s",
            conversation.id,
            message.id,
        )
        _trigger_agent_reply(db, workspace_id, conversation, message)
    elif is_new:
        logger.info(
            "whatsapp_auto_reply_skip conversation_id=%s reason=ai_disabled",
            conversation.id,
        )

    return message


def _get_or_create_contact(
    db: Session,
    workspace_id: uuid.UUID,
    msg: WhatsAppInboundMessage,
) -> Contact:
    wa_id = msg.from_wa_id
    external_id = f"whatsapp:{wa_id}"
    profile_name = msg.contact.profile_name if msg.contact else None

    contact = db.scalar(
        select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.external_id == external_id,
        )
    )

    if contact is None:
        name = profile_name or wa_id
        contact = Contact(
            workspace_id=workspace_id,
            name=name,
            phone=f"+{wa_id}",
            external_id=external_id,
            metadata_json={
                "source": "whatsapp",
                "whatsapp": {
                    "wa_id": wa_id,
                    "profile_name": profile_name,
                },
            },
        )
        db.add(contact)
        db.flush()
        logger.info(
            "whatsapp_inbound created contact external_id=%s workspace=%s",
            external_id,
            workspace_id,
        )
    else:
        # Update name if it was set to the raw wa_id (default fallback) and a real
        # profile name is now available.
        if profile_name and contact.name == wa_id:
            contact.name = profile_name
            contact.updated_at = datetime.now(timezone.utc)
            db.flush()

    return contact


def _get_or_create_conversation(
    db: Session,
    workspace_id: uuid.UUID,
    contact: Contact,
    agent_id: uuid.UUID | None,
    channel_id: uuid.UUID | None = None,
    auto_reply_enabled: bool = False,
) -> Conversation:
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

    if conversation is None:
        from app.services.plan_service import count_new_conversation  # noqa: PLC0415

        count_new_conversation(db, workspace_id)
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            workspace_id=workspace_id,
            contact_id=contact.id,
            agent_id=agent_id,
            channel_id=channel_id,
            channel_type="whatsapp",
            status="open",
            ai_enabled=auto_reply_enabled,
            assigned_user_id=None,
            created_at=now,
            updated_at=now,
        )
        db.add(conversation)
        db.flush()
        ensure_conversation_pipeline_entry(db, conversation)
        logger.info(
            "whatsapp_inbound created conversation id=%s workspace=%s contact=%s ai_enabled=%s",
            conversation.id,
            workspace_id,
            contact.id,
            auto_reply_enabled,
        )
    else:
        # Existing conversation: respect human takeover (assigned_user_id is set).
        # If no human has taken over and the channel now has auto_reply_enabled,
        # sync ai_enabled=True so conversations created before the feature was turned
        # on can also receive automatic replies.
        if (
            auto_reply_enabled
            and not conversation.ai_enabled
            and conversation.assigned_user_id is None
        ):
            conversation.ai_enabled = True
            db.flush()
            logger.info(
                "whatsapp_inbound synced ai_enabled=True on existing conversation id=%s",
                conversation.id,
            )

    return conversation


def _create_message_idempotent(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    msg: WhatsAppInboundMessage,
    channel: Channel,
) -> tuple[ConversationMessage, bool]:
    """
    Create the inbound message if it doesn't already exist.

    Returns (message, is_new) where is_new=False indicates a duplicate wamid.
    """
    # Idempotency check: reject duplicate wamid within this conversation.
    existing = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation.id,
            ConversationMessage.external_message_id == msg.wamid,
        )
    )
    if existing is not None:
        logger.info(
            "whatsapp_inbound duplicate wamid=%s conversation=%s — skipped",
            msg.wamid,
            conversation.id,
        )
        return existing, False

    now = datetime.now(timezone.utc)
    metadata_json: dict = {
        "whatsapp_timestamp": msg.timestamp,
        "wa_id": msg.from_wa_id,
    }

    content_type = "text"
    # An image with no caption still needs non-empty content — see
    # conversation_context_builder._fetch_history, which excludes rows with
    # content == "" from the LLM history entirely.
    content = msg.text_body

    if msg.message_type == "image":
        content_type = "image"
        content = msg.text_body or "[Imagem]"

    media_key = (
        _download_inbound_media(db, channel, msg)
        if msg.message_type in ("image", "audio")
        else None
    )
    if media_key is not None:
        metadata_json["media_mime_type"] = media_key[1]

    if msg.message_type == "audio":
        content_type = "audio"
        content = _transcribe_or_placeholder(db, workspace_id, media_key)

    message = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction="inbound",
        sender_type="customer",
        content_type=content_type,
        content=content,
        media_url=media_key[0] if media_key is not None else None,
        external_message_id=msg.wamid,
        metadata_json=metadata_json,
    )
    db.add(message)

    conversation.last_message_at = now
    conversation.last_customer_message_at = now
    conversation.updated_at = now
    db.flush()

    db.commit()
    db.refresh(message)

    logger.info(
        "whatsapp_inbound message created id=%s wamid=%s conversation=%s",
        message.id,
        msg.wamid,
        conversation.id,
    )
    return message, True


def _download_inbound_media(
    db: Session,
    channel: Channel,
    msg: WhatsAppInboundMessage,
) -> tuple[str, str] | None:
    """
    Best-effort download of inbound media (image or audio) via the channel's
    provider.

    Returns (storage_key, mime_type), or None if the provider isn't
    Evolution API (only provider supported so far — conversation-image-
    upload-prd.md / whatsapp-voice-groq-elevenlabs-prd.md scoped Meta Cloud
    API's own media download as future work) or the download failed for any
    reason. Never raises: a media download failure must not prevent the
    text/caption/transcript message from being persisted.
    """
    provider = (channel.config_json or {}).get("provider")
    if provider != "evolution_api":
        logger.info(
            "whatsapp_inbound media download skipped provider=%s wamid=%s "
            "(only evolution_api is supported today)",
            provider,
            msg.wamid,
        )
        return None

    from app.services.evolution_media_service import (  # noqa: PLC0415
        download_and_store_inbound_media,
    )
    from app.services.storage.factory import get_storage_provider  # noqa: PLC0415

    storage = get_storage_provider()
    media_kind = "audio" if msg.message_type == "audio" else "image"
    return download_and_store_inbound_media(
        db, channel, storage, wamid=msg.wamid, from_wa_id=msg.from_wa_id, media_kind=media_kind
    )


def _transcribe_or_placeholder(
    db: Session,
    workspace_id: uuid.UUID,
    media_key: tuple[str, str] | None,
) -> str:
    """
    Transcribe a downloaded voice note via the workspace's own Groq key.

    Falls back to an explanatory placeholder (never empty, never invented
    content) when: the audio couldn't be downloaded, the workspace has no
    Groq key configured, or the transcription call itself failed.
    """
    if media_key is None:
        return "[Áudio recebido — não foi possível baixar o arquivo]"

    from app.services.workspace_credentials_service import (  # noqa: PLC0415
        get_workspace_credential,
    )

    groq_key = get_workspace_credential(db, workspace_id, "groq")
    if not groq_key:
        return (
            "[Áudio recebido — transcrição não configurada. "
            "Configure sua chave Groq em Configurações > Integrações.]"
        )

    from app.services.groq_transcription_service import transcribe_audio  # noqa: PLC0415
    from app.services.storage.factory import get_storage_provider  # noqa: PLC0415

    storage_key, mime_type = media_key
    try:
        audio_bytes = get_storage_provider().get_file(storage_key)
    except Exception:
        logger.exception("whatsapp_inbound audio fetch for transcription failed key=%s", storage_key)
        return "[Áudio recebido — não foi possível ler o arquivo para transcrever]"

    transcript = transcribe_audio(groq_key, audio_bytes, content_type=mime_type)
    if not transcript:
        return "[Áudio recebido — a transcrição falhou]"
    return transcript


def _trigger_agent_reply(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    trigger_message: ConversationMessage,
) -> None:
    """Schedule auto-reply via debounce scheduler; errors are logged and never propagate."""
    try:
        from sqlalchemy import select as _select  # noqa: PLC0415

        from app.models.agent_prompt_settings import AgentPromptSettings  # noqa: PLC0415
        from app.services.auto_reply_scheduler import schedule_agent_auto_reply  # noqa: PLC0415

        prompt_cfg = db.scalar(
            _select(AgentPromptSettings).where(
                AgentPromptSettings.agent_id == conversation.agent_id
            )
        )
        delay = int(getattr(prompt_cfg, "reply_delay_seconds", 0) or 0)
        schedule_agent_auto_reply(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            agent_id=conversation.agent_id,
            trigger_message_id=trigger_message.id,
            delay_seconds=delay,
            db=db,
        )
    except Exception:
        logger.exception(
            "whatsapp_inbound auto-reply scheduling failed conversation=%s message=%s",
            conversation.id,
            trigger_message.id,
        )
