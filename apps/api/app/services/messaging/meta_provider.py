"""Meta Cloud API outbound provider.

Thin adapter over the existing ``whatsapp_outbound_service``. It calls the
delegate through the module attribute (not a bound ``from ... import``) so tests
that patch ``app.services.whatsapp_outbound_service.deliver_human_message`` keep
intercepting the call.
"""

import logging

import httpx
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services import whatsapp_outbound_service

logger = logging.getLogger(__name__)

PROVIDER_KEY = "meta_cloud_api"
_META_API_BASE = "https://graph.facebook.com/v21.0"
_META_API_TIMEOUT = 10.0


class MetaOutboundProvider:
    """Delivers outbound messages via the WhatsApp Cloud API (Meta)."""

    provider_key = PROVIDER_KEY

    def deliver(
        self,
        db: Session,
        message: ConversationMessage,
        conversation: Conversation,
    ) -> None:
        whatsapp_outbound_service.deliver_human_message(db, message, conversation)

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
        """
        Deliver an image via Meta Graph API (link-based — Meta fetches the
        media itself from a presigned URL, unlike Evolution's base64 upload).

        Audio replies are out of scope for Meta in this PRD slice — the Meta
        channel isn't in active production use yet (pending app approval),
        so building/testing Meta voice-message delivery isn't a priority.
        Logs and records a failure rather than silently doing nothing.
        """
        if message.content_type != "image":
            logger.warning(
                "meta_outbound_media unsupported content_type=%s message_id=%s "
                "(only image delivery is implemented for Meta today)",
                message.content_type,
                message.id,
            )
            _save_meta_media_failure(message, "unsupported_content_type")
            db.commit()
            return

        channel = whatsapp_outbound_service._find_whatsapp_channel(db, conversation)  # noqa: SLF001
        contact = whatsapp_outbound_service._load_contact(db, conversation)  # noqa: SLF001
        recipient = (
            whatsapp_outbound_service.normalize_whatsapp_to(contact) if contact else None
        )
        token = (
            whatsapp_outbound_service._resolve_access_token(db, channel)  # noqa: SLF001
            if channel else None
        )
        phone_number_id = (getattr(channel, "config_json", None) or {}).get("phone_number_id")

        if not (channel and recipient and token and phone_number_id):
            _save_meta_media_failure(message, "missing_channel_or_recipient_or_token")
            db.commit()
            return

        from app.services.storage.factory import get_storage_provider  # noqa: PLC0415

        try:
            image_url = get_storage_provider().generate_presigned_url(storage_key, expires_in=3600)
        except Exception as exc:
            _save_meta_media_failure(message, f"presigned_url_failed:{exc}")
            db.commit()
            return

        try:
            response = _call_meta_image_api(
                phone_number_id=phone_number_id,
                to=recipient,
                image_url=image_url,
                caption=caption,
                token=token,
            )
        except Exception as exc:
            _save_meta_media_failure(message, str(exc)[:300])
            db.commit()
            return

        messages = response.get("messages") if isinstance(response, dict) else None
        wamid = messages[0].get("id") if isinstance(messages, list) and messages else None
        if not wamid:
            _save_meta_media_failure(message, "meta_response_missing_message_id")
            db.commit()
            return

        message.external_message_id = wamid
        existing = message.metadata_json or {}
        message.metadata_json = {**existing, "delivery": {"status": "sent", "wamid": wamid}}
        db.commit()


def _call_meta_image_api(
    phone_number_id: str,
    to: str,
    image_url: str,
    caption: str | None,
    token: str,
) -> dict:
    url = f"{_META_API_BASE}/{phone_number_id}/messages"
    image_payload: dict = {"link": image_url}
    if caption:
        image_payload["caption"] = caption
    response = httpx.post(
        url,
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": image_payload,
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=_META_API_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _save_meta_media_failure(message: ConversationMessage, reason: str) -> None:
    existing = message.metadata_json or {}
    message.metadata_json = {**existing, "delivery": {"status": "failed", "error": reason}}
