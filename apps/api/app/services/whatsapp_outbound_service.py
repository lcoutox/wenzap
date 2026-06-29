"""
WhatsApp outbound delivery service — Phase 6.3-A.

Delivers outbound/human messages from the Inbox to WhatsApp Cloud API.

Design notes:
- deliver_human_message() never raises. All errors are caught, logged, and
  recorded in metadata_json.delivery so the Inbox message is never lost.
- Access tokens are resolved from environment variables via access_token_ref.
  The actual token value is never logged.
- channel_id on the conversation is the preferred lookup path; workspace+agent
  is used as a fallback for conversations created before this migration.
"""

import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage

logger = logging.getLogger(__name__)

_META_API_BASE = "https://graph.facebook.com/v21.0"
_META_API_TIMEOUT = 10.0


# ── Public API ─────────────────────────────────────────────────────────────────


def deliver_human_message(
    db: Session,
    message: ConversationMessage,
    conversation: Conversation,
) -> None:
    """
    Attempt to deliver an outbound message via WhatsApp Cloud API.

    Updates message.external_message_id and message.metadata_json with the
    delivery outcome. Never raises — all errors are caught and recorded.
    """
    try:
        _deliver(db, message, conversation)
    except Exception:
        logger.exception(
            "whatsapp_outbound unexpected error message_id=%s conversation_id=%s",
            message.id,
            conversation.id,
        )
        _save_delivery_failure(
            db, message,
            error_type="unexpected_error",
            error_message="An unexpected error occurred during delivery.",
            phone_number_id=None,
            recipient=None,
        )


def normalize_whatsapp_to(contact: Contact) -> str | None:
    """
    Extract the WhatsApp recipient number from a Contact.

    Returns the number in Meta's expected format: digits only, no '+'.
    Example: '5537999999999'

    Prefers external_id ('whatsapp:5537999999999') over phone ('+5537999999999').
    Returns None if neither field yields a usable number.
    """
    if contact.external_id and contact.external_id.startswith("whatsapp:"):
        wa_id = contact.external_id.removeprefix("whatsapp:")
        if wa_id:
            return wa_id

    if contact.phone:
        stripped = contact.phone.lstrip("+")
        if stripped:
            return stripped

    return None


# ── Private orchestration ──────────────────────────────────────────────────────


def _deliver(
    db: Session,
    message: ConversationMessage,
    conversation: Conversation,
) -> None:
    channel = _find_whatsapp_channel(db, conversation)
    phone_number_id = (channel.config_json or {}).get("phone_number_id") if channel else None

    if channel is None:
        logger.warning(
            "whatsapp_outbound channel not found conversation_id=%s", conversation.id
        )
        _save_delivery_failure(
            db, message,
            error_type="channel_not_found",
            error_message="No active WhatsApp channel found for this conversation.",
            phone_number_id=None,
            recipient=None,
        )
        return

    contact = _load_contact(db, conversation)
    recipient = normalize_whatsapp_to(contact) if contact else None

    if not recipient:
        logger.warning(
            "whatsapp_outbound missing recipient conversation_id=%s contact_id=%s",
            conversation.id,
            conversation.contact_id,
        )
        _save_delivery_failure(
            db, message,
            error_type="missing_recipient",
            error_message="Contact has no usable WhatsApp number.",
            phone_number_id=phone_number_id,
            recipient=None,
        )
        return

    token = _resolve_access_token(channel)
    if not token:
        logger.warning(
            "whatsapp_outbound missing token channel_id=%s", channel.id
        )
        _save_delivery_failure(
            db, message,
            error_type="missing_token",
            error_message="WhatsApp access token not configured for this channel.",
            phone_number_id=phone_number_id,
            recipient=recipient,
        )
        return

    try:
        response = _call_meta_cloud_api(
            phone_number_id=phone_number_id,
            to=recipient,
            body=message.content,
            token=token,
        )
    except httpx.TimeoutException:
        logger.warning(
            "whatsapp_outbound timeout message_id=%s", message.id
        )
        _save_delivery_failure(
            db, message,
            error_type="timeout",
            error_message="Meta Cloud API request timed out.",
            phone_number_id=phone_number_id,
            recipient=recipient,
        )
        return
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.warning(
            "whatsapp_outbound http_error status=%s message_id=%s",
            status_code,
            message.id,
        )
        _save_delivery_failure(
            db, message,
            error_type="http_error",
            error_status=status_code,
            error_message=_safe_meta_error_message(exc),
            phone_number_id=phone_number_id,
            recipient=recipient,
        )
        return
    except httpx.RequestError as exc:
        logger.warning(
            "whatsapp_outbound request_error message_id=%s error=%s",
            message.id,
            type(exc).__name__,
        )
        _save_delivery_failure(
            db, message,
            error_type="request_error",
            error_message=type(exc).__name__,
            phone_number_id=phone_number_id,
            recipient=recipient,
        )
        return

    messages = response.get("messages") if isinstance(response, dict) else None
    wamid = (messages[0].get("id") if messages else None) if isinstance(messages, list) else None

    if not wamid:
        logger.warning(
            "whatsapp_outbound missing wamid in response message_id=%s", message.id
        )
        _save_delivery_failure(
            db, message,
            error_type="missing_wamid",
            error_message="Meta response did not include a message id.",
            phone_number_id=phone_number_id,
            recipient=recipient,
        )
        return

    _save_delivery_success(
        db, message,
        wamid=wamid,
        phone_number_id=phone_number_id,
        recipient=recipient,
    )
    logger.info(
        "whatsapp_outbound delivered message_id=%s wamid=%s", message.id, wamid
    )


def _find_whatsapp_channel(db: Session, conversation: Conversation) -> Channel | None:
    # Prefer the channel linked directly to this conversation.
    if conversation.channel_id is not None:
        ch = db.get(Channel, conversation.channel_id)
        if ch and ch.channel_type == "whatsapp" and ch.status != "archived":
            return ch

    # Fallback for conversations created before the channel_id migration.
    return db.scalar(
        select(Channel).where(
            Channel.workspace_id == conversation.workspace_id,
            Channel.agent_id == conversation.agent_id,
            Channel.channel_type == "whatsapp",
            Channel.status == "active",
        )
    )


def _load_contact(db: Session, conversation: Conversation) -> Contact | None:
    if conversation.contact_id is None:
        return None
    return db.get(Contact, conversation.contact_id)


def _resolve_access_token(channel: Channel) -> str | None:
    ref = (channel.config_json or {}).get("access_token_ref")
    if not ref:
        return None
    if ref.startswith("env:"):
        var_name = ref.removeprefix("env:")
        return os.environ.get(var_name) or None
    logger.warning("whatsapp_outbound unknown token ref format channel_id=%s", channel.id)
    return None


def _call_meta_cloud_api(
    phone_number_id: str,
    to: str,
    body: str,
    token: str,
) -> dict:
    url = f"{_META_API_BASE}/{phone_number_id}/messages"
    response = httpx.post(
        url,
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": body},
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=_META_API_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _safe_meta_error_message(exc: httpx.HTTPStatusError) -> str:
    """Extract a safe, readable error message from a Meta API HTTP error response."""
    try:
        body = exc.response.json()
        msg = (body.get("error") or {}).get("message", "")
        if msg:
            return str(msg)[:300]
    except Exception:
        pass
    return exc.response.text[:200]


def _save_delivery_success(
    db: Session,
    message: ConversationMessage,
    wamid: str,
    phone_number_id: str | None,
    recipient: str | None,
) -> None:
    message.external_message_id = wamid
    existing = message.metadata_json or {}
    message.metadata_json = {
        **existing,
        "delivery": {
            "channel": "whatsapp",
            "provider": "meta_cloud_api",
            "status": "sent",
            "external_message_id": wamid,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "phone_number_id": phone_number_id,
            "recipient": recipient,
        },
    }
    db.commit()


def _save_delivery_failure(
    db: Session,
    message: ConversationMessage,
    error_type: str,
    error_message: str,
    phone_number_id: str | None,
    recipient: str | None,
    error_status: int | None = None,
) -> None:
    existing = message.metadata_json or {}
    message.metadata_json = {
        **existing,
        "delivery": {
            "channel": "whatsapp",
            "provider": "meta_cloud_api",
            "status": "failed",
            "error_type": error_type,
            "error_status": error_status,
            "error_message": error_message,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "phone_number_id": phone_number_id,
            "recipient": recipient,
        },
    }
    db.commit()


def _should_deliver(message: ConversationMessage, conversation: Conversation) -> bool:
    return (
        conversation.channel_type == "whatsapp"
        and message.direction == "outbound"
        and message.sender_type == "human"
    )
