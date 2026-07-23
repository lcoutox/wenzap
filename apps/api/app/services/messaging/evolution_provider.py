"""Evolution API outbound provider — bridge (unofficial WhatsApp).

Used as a bridge provider until Meta approves the app for multi-tenant
WhatsApp Embedded Signup. Delivers via a self-hosted Evolution API server
(one Evolution "instance" per connected number, per channel).

Design notes (mirrors whatsapp_outbound_service's contract):
- deliver() never raises. All errors are caught, logged, and recorded in
  message.metadata_json.delivery so the Inbox message is never lost.
- The instance API key is resolved via resolve_channel_secret() — same
  env:/db: reference mechanism used for Meta tokens.
- Payload shape targets Evolution API v2. This has NOT yet been smoke-tested
  against a live instance — verify against the real server response before
  fully trusting delivery in production (see plano-evolution-api.md).
"""

import base64
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.channel_credentials_service import resolve_channel_secret
from app.services.whatsapp_outbound_service import _load_contact, normalize_whatsapp_to

logger = logging.getLogger(__name__)

PROVIDER_KEY = "evolution_api"
_TIMEOUT = 10.0
_MEDIA_TIMEOUT = 20.0  # media uploads take longer than a plain text send


class EvolutionOutboundProvider:
    """Delivers outbound messages via a self-hosted Evolution API instance."""

    provider_key = PROVIDER_KEY

    def deliver(
        self,
        db: Session,
        message: ConversationMessage,
        conversation: Conversation,
    ) -> None:
        try:
            _deliver(db, message, conversation)
        except Exception:
            logger.exception(
                "evolution_outbound unexpected error message_id=%s conversation_id=%s",
                message.id,
                conversation.id,
            )
            _save_delivery_failure(
                db, message,
                error_type="unexpected_error",
                error_message="An unexpected error occurred during delivery.",
                instance_name=None,
                recipient=None,
            )

    def deliver_media(
        self,
        db: Session,
        message: ConversationMessage,
        conversation: Conversation,
        *,
        storage_key: str,
        mime_type: str,
        caption: str | None = None,
    ) -> None:
        try:
            _deliver_media(db, message, conversation, storage_key=storage_key, mime_type=mime_type, caption=caption)
        except Exception:
            logger.exception(
                "evolution_outbound_media unexpected error message_id=%s conversation_id=%s",
                message.id,
                conversation.id,
            )
            _save_delivery_failure(
                db, message,
                error_type="unexpected_error",
                error_message="An unexpected error occurred during media delivery.",
                instance_name=None,
                recipient=None,
            )


# ── Private orchestration ──────────────────────────────────────────────────────


def _find_whatsapp_channel(db: Session, conversation: Conversation) -> Channel | None:
    if conversation.channel_id is not None:
        ch = db.get(Channel, conversation.channel_id)
        if ch and ch.channel_type == "whatsapp" and ch.status != "archived":
            return ch
    return db.scalar(
        select(Channel).where(
            Channel.workspace_id == conversation.workspace_id,
            Channel.agent_id == conversation.agent_id,
            Channel.channel_type == "whatsapp",
            Channel.status == "active",
        )
    )


def _deliver(
    db: Session,
    message: ConversationMessage,
    conversation: Conversation,
) -> None:
    channel = _find_whatsapp_channel(db, conversation)
    config = (channel.config_json or {}) if channel else {}
    base_url = config.get("base_url")
    instance_name = config.get("instance_name")

    if channel is None:
        logger.warning(
            "evolution_outbound channel not found conversation_id=%s", conversation.id
        )
        _save_delivery_failure(
            db, message,
            error_type="channel_not_found",
            error_message="No active WhatsApp channel found for this conversation.",
            instance_name=None,
            recipient=None,
        )
        return

    contact = _load_contact(db, conversation)
    recipient = normalize_whatsapp_to(contact) if contact else None

    if not recipient:
        logger.warning(
            "evolution_outbound missing recipient conversation_id=%s contact_id=%s",
            conversation.id,
            conversation.contact_id,
        )
        _save_delivery_failure(
            db, message,
            error_type="missing_recipient",
            error_message="Contact has no usable WhatsApp number.",
            instance_name=instance_name,
            recipient=None,
        )
        return

    if not base_url or not instance_name:
        logger.warning(
            "evolution_outbound missing base_url/instance_name channel_id=%s", channel.id
        )
        _save_delivery_failure(
            db, message,
            error_type="missing_instance_config",
            error_message="Evolution base_url or instance_name not configured for this channel.",
            instance_name=instance_name,
            recipient=recipient,
        )
        return

    api_key = _resolve_api_key(db, channel, config.get("api_key_ref"))
    if not api_key:
        logger.warning(
            "evolution_outbound missing api key channel_id=%s", channel.id
        )
        _save_delivery_failure(
            db, message,
            error_type="missing_api_key",
            error_message="Evolution API key not configured for this channel.",
            instance_name=instance_name,
            recipient=recipient,
        )
        return

    try:
        response = _call_evolution_send_text(
            base_url=base_url,
            instance_name=instance_name,
            to=recipient,
            body=message.content,
            api_key=api_key,
        )
    except httpx.TimeoutException:
        logger.warning("evolution_outbound timeout message_id=%s", message.id)
        _save_delivery_failure(
            db, message,
            error_type="timeout",
            error_message="Evolution API request timed out.",
            instance_name=instance_name,
            recipient=recipient,
        )
        return
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.warning(
            "evolution_outbound http_error status=%s message_id=%s", status_code, message.id
        )
        _save_delivery_failure(
            db, message,
            error_type="http_error",
            error_status=status_code,
            error_message=_safe_error_message(exc),
            instance_name=instance_name,
            recipient=recipient,
        )
        return
    except httpx.RequestError as exc:
        logger.warning(
            "evolution_outbound request_error message_id=%s error=%s",
            message.id,
            type(exc).__name__,
        )
        _save_delivery_failure(
            db, message,
            error_type="request_error",
            error_message=type(exc).__name__,
            instance_name=instance_name,
            recipient=recipient,
        )
        return

    # Evolution's response shape for message id is not yet confirmed against a
    # live instance — extract defensively and accept a 2xx response as "sent"
    # even if no id-like field is found, rather than risk false failures.
    external_id = _extract_message_id(response)

    _save_delivery_success(
        db, message,
        external_id=external_id,
        instance_name=instance_name,
        recipient=recipient,
    )
    logger.info(
        "evolution_outbound delivered message_id=%s external_id=%s", message.id, external_id
    )


def _deliver_media(
    db: Session,
    message: ConversationMessage,
    conversation: Conversation,
    *,
    storage_key: str,
    mime_type: str,
    caption: str | None,
) -> None:
    channel = _find_whatsapp_channel(db, conversation)
    config = (channel.config_json or {}) if channel else {}
    base_url = config.get("base_url")
    instance_name = config.get("instance_name")

    if channel is None:
        logger.warning("evolution_outbound_media channel not found conversation_id=%s", conversation.id)
        _save_delivery_failure(
            db, message,
            error_type="channel_not_found",
            error_message="No active WhatsApp channel found for this conversation.",
            instance_name=None,
            recipient=None,
        )
        return

    contact = _load_contact(db, conversation)
    recipient = normalize_whatsapp_to(contact) if contact else None
    if not recipient:
        _save_delivery_failure(
            db, message,
            error_type="missing_recipient",
            error_message="Contact has no usable WhatsApp number.",
            instance_name=instance_name,
            recipient=None,
        )
        return

    if not base_url or not instance_name:
        _save_delivery_failure(
            db, message,
            error_type="missing_instance_config",
            error_message="Evolution base_url or instance_name not configured for this channel.",
            instance_name=instance_name,
            recipient=recipient,
        )
        return

    api_key = _resolve_api_key(db, channel, config.get("api_key_ref"))
    if not api_key:
        _save_delivery_failure(
            db, message,
            error_type="missing_api_key",
            error_message="Evolution API key not configured for this channel.",
            instance_name=instance_name,
            recipient=recipient,
        )
        return

    from app.services.storage.factory import get_storage_provider  # noqa: PLC0415

    try:
        data = get_storage_provider().get_file(storage_key)
    except Exception as exc:
        logger.exception("evolution_outbound_media storage fetch failed key=%s", storage_key)
        _save_delivery_failure(
            db, message,
            error_type="storage_fetch_failed",
            error_message=str(exc)[:300],
            instance_name=instance_name,
            recipient=recipient,
        )
        return

    encoded = base64.b64encode(data).decode("ascii")

    try:
        if message.content_type == "audio":
            response = _call_evolution_send_audio(
                base_url=base_url, instance_name=instance_name, to=recipient,
                audio_base64=encoded, api_key=api_key,
            )
        else:
            response = _call_evolution_send_media(
                base_url=base_url, instance_name=instance_name, to=recipient,
                media_base64=encoded, mime_type=mime_type, caption=caption, api_key=api_key,
            )
    except httpx.TimeoutException:
        _save_delivery_failure(
            db, message,
            error_type="timeout",
            error_message="Evolution API media request timed out.",
            instance_name=instance_name,
            recipient=recipient,
        )
        return
    except httpx.HTTPStatusError as exc:
        _save_delivery_failure(
            db, message,
            error_type="http_error",
            error_status=exc.response.status_code,
            error_message=_safe_error_message(exc),
            instance_name=instance_name,
            recipient=recipient,
        )
        return
    except httpx.RequestError as exc:
        _save_delivery_failure(
            db, message,
            error_type="request_error",
            error_message=type(exc).__name__,
            instance_name=instance_name,
            recipient=recipient,
        )
        return

    external_id = _extract_message_id(response)
    _save_delivery_success(
        db, message, external_id=external_id, instance_name=instance_name, recipient=recipient
    )
    logger.info(
        "evolution_outbound_media delivered message_id=%s external_id=%s content_type=%s",
        message.id, external_id, message.content_type,
    )


def _call_evolution_send_audio(
    base_url: str,
    instance_name: str,
    to: str,
    audio_base64: str,
    api_key: str,
) -> dict:
    """POST {base_url}/message/sendWhatsAppAudio/{instance_name} (Evolution API v2 shape).

    ⚠️ Not yet smoke-tested against a live Evolution instance.
    """
    url = f"{base_url.rstrip('/')}/message/sendWhatsAppAudio/{instance_name}"
    response = httpx.post(
        url,
        json={"number": to, "audio": audio_base64, "encoding": True},
        headers={"apikey": api_key, "Content-Type": "application/json"},
        timeout=_MEDIA_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _call_evolution_send_media(
    base_url: str,
    instance_name: str,
    to: str,
    media_base64: str,
    mime_type: str,
    caption: str | None,
    api_key: str,
) -> dict:
    """POST {base_url}/message/sendMedia/{instance_name} (Evolution API v2 shape).

    Used for images (catalog delivery). ⚠️ Not yet smoke-tested against a
    live Evolution instance.
    """
    url = f"{base_url.rstrip('/')}/message/sendMedia/{instance_name}"
    payload: dict = {
        "number": to,
        "mediatype": "image",
        "mimetype": mime_type,
        "media": media_base64,
    }
    if caption:
        payload["caption"] = caption
    response = httpx.post(
        url,
        json=payload,
        headers={"apikey": api_key, "Content-Type": "application/json"},
        timeout=_MEDIA_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _resolve_api_key(db: Session, channel: Channel, ref: str | None) -> str | None:
    if not ref:
        return None
    return resolve_channel_secret(db, channel, ref)


def _call_evolution_send_text(
    base_url: str,
    instance_name: str,
    to: str,
    body: str,
    api_key: str,
) -> dict:
    """POST {base_url}/message/sendText/{instance_name} (Evolution API v2 shape).

    ⚠️ Not yet smoke-tested against a live Evolution instance — confirm the
    request/response shape and adjust if the deployed version differs.
    """
    url = f"{base_url.rstrip('/')}/message/sendText/{instance_name}"
    response = httpx.post(
        url,
        json={"number": to, "text": body},
        headers={"apikey": api_key, "Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _extract_message_id(response: dict) -> str | None:
    if not isinstance(response, dict):
        return None
    key = response.get("key")
    if isinstance(key, dict) and key.get("id"):
        return str(key["id"])
    if response.get("id"):
        return str(response["id"])
    return None


def _safe_error_message(exc: httpx.HTTPStatusError) -> str:
    try:
        body = exc.response.json()
        msg = body.get("message") or body.get("error") or ""
        if msg:
            return str(msg)[:300]
    except Exception:
        pass
    return exc.response.text[:200]


def _save_delivery_success(
    db: Session,
    message: ConversationMessage,
    external_id: str | None,
    instance_name: str | None,
    recipient: str | None,
) -> None:
    if external_id:
        message.external_message_id = external_id
    existing = message.metadata_json or {}
    message.metadata_json = {
        **existing,
        "delivery": {
            "channel": "whatsapp",
            "provider": PROVIDER_KEY,
            "status": "sent",
            "external_message_id": external_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "instance_name": instance_name,
            "recipient": recipient,
        },
    }
    db.commit()


def _save_delivery_failure(
    db: Session,
    message: ConversationMessage,
    error_type: str,
    error_message: str,
    instance_name: str | None,
    recipient: str | None,
    error_status: int | None = None,
) -> None:
    existing = message.metadata_json or {}
    message.metadata_json = {
        **existing,
        "delivery": {
            "channel": "whatsapp",
            "provider": PROVIDER_KEY,
            "status": "failed",
            "error_type": error_type,
            "error_status": error_status,
            "error_message": error_message,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "instance_name": instance_name,
            "recipient": recipient,
        },
    }
    db.commit()

