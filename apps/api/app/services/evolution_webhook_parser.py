"""Parser for Evolution API webhook payloads (WHATSAPP-BAILEYS integration).

Pure functions — no DB access, no side effects. Translates the Evolution
`messages.upsert` event shape into the same WhatsAppInboundMessage dataclass
used by the Meta parser, so the rest of the inbound pipeline
(whatsapp_inbound_service) stays provider-agnostic.

Payload shape confirmed against a live Evolution v2.3.7 instance on
2026-07-13 (see negocios/wenzap/plano-evolution-api.md for the raw capture):

{
  "event": "messages.upsert",
  "instance": "wenzap",
  "data": {
    "key": {"remoteJid": "553784111441@s.whatsapp.net", "fromMe": false, "id": "..."},
    "pushName": "Lucas Couto",
    "message": {"conversation": "Boa noite"},
    "messageType": "conversation",
    "messageTimestamp": 1783982199
  },
  "apikey": "..."
}

Note on `WhatsAppInboundMessage.phone_number_id`: for Evolution this field
holds the *instance name* (the Evolution routing key), not a Meta
phone_number_id. It is used only for logging here — the caller
(evolution_webhooks router) resolves the channel by instance name before
processing, so the field isn't used for lookup in this path.

Image messages (conversation-image-upload-prd.md, 2026-07-20): recognized
here (`messageType == "imageMessage"`) but this parser only extracts the
caption + routing info — the actual media bytes are fetched separately by
evolution_media_service.py (Evolution's own `getBase64FromMediaMessage`
endpoint handles the Baileys media decryption; this parser never touches
the encrypted `message.imageMessage.url`). ⚠️ The exact shape of
`message.imageMessage` (caption field name, presence of a mimetype hint)
has NOT been confirmed against a live payload the way the text shape above
was — verify against a real image message before fully trusting this.
"""

import logging

from app.services.whatsapp_webhook_parser import WhatsAppContact, WhatsAppInboundMessage

logger = logging.getLogger(__name__)

# Message types that carry plain, extractable text.
_TEXT_MESSAGE_TYPES = {"conversation", "extendedTextMessage"}

# Image message type (Baileys/Evolution naming). Other media types (document,
# audio, video, sticker) are still ignored — see novas-funcionalidades-chatvolt.md
# in NexBrain for that broader (not yet built) scope.
_IMAGE_MESSAGE_TYPE = "imageMessage"


def parse_inbound_text_messages(payload: object) -> list[WhatsAppInboundMessage]:
    """
    Extract inbound (not self-sent) text messages from an Evolution webhook payload.

    Ignores: non-messages.upsert events, fromMe=true (our own sends echoed back
    by Evolution), non-text message types, and malformed structures. Never raises.
    """
    if not isinstance(payload, dict):
        return []

    if payload.get("event") != "messages.upsert":
        return []

    instance_name = payload.get("instance")
    if not instance_name:
        return []

    raw_data = payload.get("data")
    entries = raw_data if isinstance(raw_data, list) else [raw_data]

    results: list[WhatsAppInboundMessage] = []
    for entry in entries:
        msg = _parse_single_message(instance_name, entry)
        if msg is not None:
            results.append(msg)
    return results


def _parse_single_message(instance_name: str, data: object) -> WhatsAppInboundMessage | None:
    if not isinstance(data, dict):
        return None

    key = data.get("key")
    if not isinstance(key, dict):
        return None

    # Evolution fires messages.upsert for BOTH inbound messages and messages we
    # sent via the API (echoed back). Skip our own sends — critical to avoid
    # processing every outbound reply as if it were a new customer message.
    if key.get("fromMe"):
        return None

    wamid = key.get("id")
    remote_jid = key.get("remoteJid")
    if not wamid or not remote_jid:
        logger.info("evolution_parser skipping message missing id or remoteJid")
        return None

    from_wa_id = str(remote_jid).split("@")[0]
    if not from_wa_id:
        return None

    message_type = data.get("messageType")
    is_image = message_type == _IMAGE_MESSAGE_TYPE
    if message_type not in _TEXT_MESSAGE_TYPES and not is_image:
        logger.info(
            "evolution_parser skipping unsupported messageType=%s wamid=%s",
            message_type,
            wamid,
        )
        return None

    text_body = _extract_text(data.get("message"))
    # An image with no caption is still valid business data — only plain
    # text messages require a non-empty body to be worth persisting.
    if not is_image and not text_body:
        logger.info("evolution_parser skipping message with empty body wamid=%s", wamid)
        return None

    timestamp_raw = data.get("messageTimestamp")
    try:
        timestamp = int(timestamp_raw) if timestamp_raw is not None else None
    except (ValueError, TypeError):
        timestamp = None

    profile_name = data.get("pushName")
    contact = WhatsAppContact(wa_id=from_wa_id, profile_name=profile_name)

    return WhatsAppInboundMessage(
        phone_number_id=instance_name,
        wamid=str(wamid),
        from_wa_id=from_wa_id,
        timestamp=timestamp,
        text_body=text_body,
        contact=contact,
        message_type="image" if is_image else "text",
    )


def _extract_text(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    conversation = message.get("conversation")
    if isinstance(conversation, str) and conversation:
        return conversation
    extended = message.get("extendedTextMessage")
    if isinstance(extended, dict):
        text = extended.get("text")
        if isinstance(text, str):
            return text
    # Image messages carry their text as an optional caption, not "conversation".
    image = message.get("imageMessage")
    if isinstance(image, dict):
        caption = image.get("caption")
        if isinstance(caption, str):
            return caption
    return ""


def extract_apikey(payload: object) -> str | None:
    """Extract the `apikey` field Evolution includes in every webhook payload.

    Used to validate the webhook against the channel's stored credential
    (see evolution_webhooks router) — not a cryptographic signature, but a
    shared-secret check with no additional configuration required.
    """
    if not isinstance(payload, dict):
        return None
    value = payload.get("apikey")
    return value if isinstance(value, str) else None
