"""
Meta Cloud API inbound media download — meta-cloud-api-parity-prd.md.

Two-step flow per Meta's own docs (developers.facebook.com/docs/whatsapp/
cloud-api/reference/media): GET /{media_id} (Bearer token) returns a
short-lived (~5 min) CDN url; GET that url (same Bearer token) returns the
raw bytes. Mirrors evolution_media_service.py's shape — same
(storage_key, mime_type) return tuple — so whatsapp_inbound_service can stay
provider-agnostic past the initial dispatch.

⚠️ Not yet smoke-tested against the real Meta Graph API — built from Meta's
published docs, same caveat as the rest of this session's media pipeline.
"""

import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.services.channel_credentials_service import resolve_channel_secret
from app.services.storage.base import StorageProvider

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0
_META_API_BASE = "https://graph.facebook.com/v21.0"
_DEFAULT_MIME_TYPE_BY_KIND = {
    "image": "image/jpeg",
    "audio": "audio/ogg",
}


def download_and_store_inbound_media(
    db: Session,
    channel: Channel,
    storage: StorageProvider,
    *,
    media_id: str,
    mime_type_hint: str | None = None,
    media_kind: str = "image",
) -> tuple[str, str] | None:
    """
    Download inbound media (image or audio) from the Meta Graph API and store it.

    Returns (storage_key, mime_type) on success, or None on any failure.
    Never raises — a media download failure must never break message
    persistence or the webhook's 200 response.
    """
    config = channel.config_json or {}
    ref = config.get("access_token_ref")
    if not ref:
        logger.warning(
            "meta_media missing access_token_ref channel_id=%s media_id=%s", channel.id, media_id
        )
        return None

    token = resolve_channel_secret(db, channel, ref)
    if not token:
        logger.warning("meta_media missing token channel_id=%s media_id=%s", channel.id, media_id)
        return None

    url_info = _fetch_media_url(media_id=media_id, token=token)
    if url_info is None:
        return None

    media_url = url_info.get("url")
    if not isinstance(media_url, str) or not media_url:
        logger.warning("meta_media response missing url media_id=%s", media_id)
        return None

    mime_type = (
        url_info.get("mime_type")
        or mime_type_hint
        or _DEFAULT_MIME_TYPE_BY_KIND.get(media_kind, "application/octet-stream")
    )

    data = _download_bytes(media_url, token, media_id)
    if data is None:
        return None

    key = _build_storage_key(channel.workspace_id, mime_type)
    try:
        storage.put_file(key, data, content_type=mime_type)
    except Exception:
        logger.exception("meta_media storage upload failed media_id=%s key=%s", media_id, key)
        return None

    logger.info(
        "meta_media downloaded and stored media_id=%s key=%s mime_type=%s size_bytes=%d",
        media_id,
        key,
        mime_type,
        len(data),
    )
    return key, mime_type


# ── Internal helpers ──────────────────────────────────────────────────────────


def _fetch_media_url(*, media_id: str, token: str) -> dict | None:
    url = f"{_META_API_BASE}/{media_id}"
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        logger.exception("meta_media url fetch failed media_id=%s", media_id)
        return None

    if not isinstance(payload, dict):
        logger.warning("meta_media unexpected response shape media_id=%s", media_id)
        return None
    return payload


def _download_bytes(media_url: str, token: str, media_id: str) -> bytes | None:
    try:
        response = httpx.get(
            media_url, headers={"Authorization": f"Bearer {token}"}, timeout=_TIMEOUT
        )
        response.raise_for_status()
        return response.content
    except Exception:
        logger.exception("meta_media bytes download failed media_id=%s", media_id)
        return None


def _build_storage_key(workspace_id: uuid.UUID, mime_type: str) -> str:
    extension = (mime_type.split("/")[-1].split(";")[0] or "jpg").strip() or "jpg"
    return f"conversation-media/{workspace_id}/{uuid.uuid4()}.{extension}"
