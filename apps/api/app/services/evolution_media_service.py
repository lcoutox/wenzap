"""
Evolution API inbound media download — conversation-image-upload-prd.md,
extended to audio by whatsapp-voice-groq-elevenlabs-prd.md.

Downloads inbound WhatsApp media (images, audio) via Evolution API's own
`getBase64FromMediaMessage` endpoint, which handles the Baileys media
decryption internally so this codebase never has to implement that crypto
itself (the raw `message.imageMessage.url`/`message.audioMessage.url` field
is an encrypted WhatsApp CDN URL — not directly downloadable without the
message's mediaKey). The endpoint is the same regardless of media type —
Evolution resolves and decrypts whatever the message actually is. Uploads
the decoded bytes to the configured StorageProvider.

⚠️ Not yet smoke-tested against a live Evolution instance — same caveat as
evolution_provider.py's _call_evolution_send_text. Confirm the request/
response shape of `getBase64FromMediaMessage` against the deployed Evolution
version (and adjust the request body / response field names below) before
fully trusting this in production. See plano-evolution-api.md.
"""

import base64
import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.services.channel_credentials_service import resolve_channel_secret
from app.services.storage.base import StorageProvider

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0
_DEFAULT_MIME_TYPE_BY_KIND = {
    "image": "image/jpeg",
    "audio": "audio/ogg",
}


def download_and_store_inbound_media(
    db: Session,
    channel: Channel,
    storage: StorageProvider,
    *,
    wamid: str,
    from_wa_id: str,
    media_kind: str = "image",
) -> tuple[str, str] | None:
    """
    Download inbound media (image or audio) from Evolution API and store it.

    *media_kind* only picks the fallback mime type used if Evolution's
    response doesn't include one — the download request itself is identical
    for any media type.

    Returns (storage_key, mime_type) on success, or None on any failure.
    Never raises — mirrors whatsapp_inbound_service's error-tolerant design;
    a media download failure must never break message persistence or the
    webhook's 200 response.
    """
    config = channel.config_json or {}
    base_url = config.get("base_url")
    instance_name = config.get("instance_name")
    if not base_url or not instance_name:
        logger.warning(
            "evolution_media missing base_url/instance_name channel_id=%s wamid=%s",
            channel.id,
            wamid,
        )
        return None

    api_key = resolve_channel_secret(db, channel, config.get("api_key_ref"))
    if not api_key:
        logger.warning("evolution_media missing api key channel_id=%s wamid=%s", channel.id, wamid)
        return None

    payload = _fetch_base64_payload(
        base_url=base_url,
        instance_name=instance_name,
        api_key=api_key,
        wamid=wamid,
        from_wa_id=from_wa_id,
    )
    if payload is None:
        return None

    base64_data = payload.get("base64") if isinstance(payload, dict) else None
    if not isinstance(base64_data, str) or not base64_data:
        logger.warning(
            "evolution_media response missing base64 wamid=%s channel_id=%s",
            wamid,
            channel.id,
        )
        return None

    mime_type = _DEFAULT_MIME_TYPE_BY_KIND.get(media_kind, "application/octet-stream")
    if isinstance(payload, dict) and isinstance(payload.get("mimetype"), str):
        mime_type = payload["mimetype"]

    try:
        data = base64.b64decode(base64_data)
    except Exception:
        logger.exception("evolution_media base64 decode failed wamid=%s", wamid)
        return None

    key = _build_storage_key(channel.workspace_id, mime_type)

    try:
        storage.put_file(key, data, content_type=mime_type)
    except Exception:
        logger.exception("evolution_media storage upload failed wamid=%s key=%s", wamid, key)
        return None

    logger.info(
        "evolution_media downloaded and stored wamid=%s key=%s mime_type=%s size_bytes=%d",
        wamid,
        key,
        mime_type,
        len(data),
    )
    return key, mime_type


def download_and_store_inbound_image(
    db: Session,
    channel: Channel,
    storage: StorageProvider,
    *,
    wamid: str,
    from_wa_id: str,
) -> tuple[str, str] | None:
    """Back-compat wrapper — see download_and_store_inbound_media."""
    return download_and_store_inbound_media(
        db, channel, storage, wamid=wamid, from_wa_id=from_wa_id, media_kind="image"
    )


def download_and_store_inbound_audio(
    db: Session,
    channel: Channel,
    storage: StorageProvider,
    *,
    wamid: str,
    from_wa_id: str,
) -> tuple[str, str] | None:
    """whatsapp-voice-groq-elevenlabs-prd.md — same download path as images."""
    return download_and_store_inbound_media(
        db, channel, storage, wamid=wamid, from_wa_id=from_wa_id, media_kind="audio"
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _fetch_base64_payload(
    *,
    base_url: str,
    instance_name: str,
    api_key: str,
    wamid: str,
    from_wa_id: str,
) -> dict | None:
    url = f"{base_url.rstrip('/')}/chat/getBase64FromMediaMessage/{instance_name}"
    try:
        response = httpx.post(
            url,
            json={
                "message": {
                    "key": {
                        "id": wamid,
                        "remoteJid": f"{from_wa_id}@s.whatsapp.net",
                        "fromMe": False,
                    }
                },
                "convertToMp4": False,
            },
            headers={"apikey": api_key, "Content-Type": "application/json"},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("evolution_media download request failed wamid=%s", wamid)
        return None

    if not isinstance(payload, dict):
        logger.warning("evolution_media unexpected response shape wamid=%s", wamid)
        return None
    return payload


def _build_storage_key(workspace_id: uuid.UUID, mime_type: str) -> str:
    extension = (mime_type.split("/")[-1].split(";")[0] or "jpg").strip() or "jpg"
    return f"conversation-media/{workspace_id}/{uuid.uuid4()}.{extension}"
