"""
Catalog Media Delivery Service — Catálogo.6.

Decides whether to send the primary image of a recommended catalog item
via WhatsApp after the agent's text reply, and performs the delivery.

Design rules (conservative by spec):
- Only on WhatsApp conversations.
- Only when agent.catalog_enabled is True.
- Only when exactly 1 catalog item was recommended with sufficient confidence.
- Only when that item has a primary image.
- Only when a public/signed URL is obtainable (not file://).
- Only once per item per conversation per 30-minute window (anti-spam).
- Text delivery must have succeeded before attempting image delivery.
- Failure never breaks the text reply — all errors are caught and logged.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog_item import CatalogItem
from app.models.catalog_media import CatalogMedia
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.catalog_retrieval_service import CatalogRetrievalItem
from app.services.storage.base import StorageProvider

logger = logging.getLogger(__name__)

_META_API_BASE = "https://graph.facebook.com/v21.0"
_META_API_TIMEOUT = 10.0
_MIN_SCORE = 0.65
_SPAM_WINDOW_MINUTES = 30
_SIGNED_URL_EXPIRY = 3600  # 1 hour — enough for Meta to fetch


# ── Decision result ───────────────────────────────────────────────────────────

@dataclass
class MediaDeliveryDecision:
    should_send: bool
    reason: str
    item_id: uuid.UUID | None = None
    media_id: uuid.UUID | None = None
    media_url: str | None = None
    caption: str | None = None


# ── Public API ────────────────────────────────────────────────────────────────

def decide_catalog_media_delivery(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    catalog_items: list[CatalogRetrievalItem],
    catalog_retrieval_attempted: bool,
    storage: StorageProvider,
    text_message: ConversationMessage,
) -> MediaDeliveryDecision:
    """
    Evaluate all criteria and return a delivery decision.

    Does NOT perform the delivery — call deliver_catalog_media_image() for that.
    """
    def _no(reason: str) -> MediaDeliveryDecision:
        return MediaDeliveryDecision(should_send=False, reason=reason)

    if conversation.channel_type != "whatsapp":
        return _no("not_whatsapp")

    if not catalog_retrieval_attempted:
        return _no("no_catalog_retrieval")

    if len(catalog_items) != 1:
        return _no("multiple_catalog_items" if catalog_items else "no_catalog_items")

    item_result = catalog_items[0]

    # Score gate — only skip if a score is present and too low.
    if item_result.score is not None and item_result.score < _MIN_SCORE:
        return _no(f"score_too_low:{item_result.score:.3f}")

    if not item_result.primary_media_available:
        return _no("no_primary_media")

    # Load the actual CatalogItem to verify status.
    catalog_item = db.scalar(
        select(CatalogItem).where(
            CatalogItem.id == item_result.id,
            CatalogItem.workspace_id == workspace_id,
        )
    )
    if catalog_item is None or catalog_item.status != "active":
        return _no("item_not_active")

    # Load primary image media.
    media = db.scalar(
        select(CatalogMedia).where(
            CatalogMedia.item_id == item_result.id,
            CatalogMedia.workspace_id == workspace_id,
            CatalogMedia.is_primary == True,  # noqa: E712
            CatalogMedia.file_type == "image",
        )
    )
    if media is None:
        return _no("primary_image_not_found")

    # Resolve a publicly accessible URL.
    try:
        url = storage.generate_presigned_url(media.file_key, expires_in=_SIGNED_URL_EXPIRY)
    except Exception:
        return _no("media_url_generation_failed")

    if url.startswith("file://"):
        return _no("media_url_not_public")

    # Anti-spam: same media_id in this conversation in the last 30 min.
    if _was_recently_sent(db, conversation.id, str(media.id)):
        return _no("recently_sent")

    caption = _build_caption(item_result)

    return MediaDeliveryDecision(
        should_send=True,
        reason="single_recommended_item_with_primary_image",
        item_id=item_result.id,
        media_id=media.id,
        media_url=url,
        caption=caption,
    )


def deliver_catalog_media_image(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    decision: MediaDeliveryDecision,
    agent_id: uuid.UUID,
    channel: object,
    contact_recipient: str,
    access_token: str,
) -> ConversationMessage | None:
    """
    Send the catalog image via WhatsApp and persist a ConversationMessage record.

    Returns the created ConversationMessage, or None if delivery was skipped/failed.
    Never raises — all errors are caught, logged, and recorded in metadata_json.
    """
    if not decision.should_send:
        return None

    phone_number_id = (
        getattr(channel, "config_json", None) or {}
    ).get("phone_number_id")

    # Persist message record first (outbound, content_type=image).
    media_msg = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_type="agent",
        agent_id=agent_id,
        content=f"[Imagem: {decision.caption or 'Produto do catálogo'}]",
        content_type="image",
        metadata_json={
            "catalog_media_delivery": {
                "attempted": True,
                "sent": False,
                "item_id": str(decision.item_id),
                "media_id": str(decision.media_id),
                "caption": decision.caption,
                "media_url": decision.media_url,
                "reason": decision.reason,
            }
        },
    )
    db.add(media_msg)
    db.flush()

    try:
        response = _call_meta_image_api(
            phone_number_id=phone_number_id,
            to=contact_recipient,
            image_url=decision.media_url,
            caption=decision.caption,
            token=access_token,
        )
    except Exception as exc:
        _record_delivery_failure(db, media_msg, decision, exc)
        return media_msg

    messages = response.get("messages") if isinstance(response, dict) else None
    wamid = (
        messages[0].get("id") if isinstance(messages, list) and messages else None
    )

    if not wamid:
        _record_delivery_failure(
            db, media_msg, decision,
            Exception("Meta response missing message id"),
        )
        return media_msg

    media_msg.external_message_id = wamid
    media_msg.metadata_json = {
        "catalog_media_delivery": {
            "attempted": True,
            "sent": True,
            "item_id": str(decision.item_id),
            "media_id": str(decision.media_id),
            "caption": decision.caption,
            "reason": decision.reason,
            "wamid": wamid,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "phone_number_id": phone_number_id,
            "recipient": contact_recipient,
        }
    }
    db.commit()

    logger.info(
        "catalog_media_delivery sent item_id=%s media_id=%s wamid=%s conversation_id=%s",
        decision.item_id, decision.media_id, wamid, conversation.id,
    )
    return media_msg


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_caption(item: CatalogRetrievalItem) -> str:
    if item.price is not None:
        price_str = f"R$ {item.price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{item.name} — {price_str}"
    return item.name


def _was_recently_sent(
    db: Session,
    conversation_id: uuid.UUID,
    media_id_str: str,
) -> bool:
    """Return True if the same media was sent in this conversation within the spam window."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=_SPAM_WINDOW_MINUTES)
    recent = db.scalars(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.direction == "outbound",
            ConversationMessage.content_type == "image",
            ConversationMessage.created_at >= cutoff,
        )
    ).all()
    for msg in recent:
        delivery = (msg.metadata_json or {}).get("catalog_media_delivery", {})
        if delivery.get("media_id") == media_id_str and delivery.get("sent") is True:
            return True
    return False


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
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=_META_API_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _record_delivery_failure(
    db: Session,
    media_msg: ConversationMessage,
    decision: MediaDeliveryDecision,
    exc: Exception,
) -> None:
    error_str = str(exc)[:300]
    logger.warning(
        "catalog_media_delivery failed item_id=%s media_id=%s error=%s",
        decision.item_id, decision.media_id, error_str,
    )
    media_msg.metadata_json = {
        "catalog_media_delivery": {
            "attempted": True,
            "sent": False,
            "item_id": str(decision.item_id),
            "media_id": str(decision.media_id),
            "caption": decision.caption,
            "reason": decision.reason,
            "error": error_str,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
    }
    db.commit()
