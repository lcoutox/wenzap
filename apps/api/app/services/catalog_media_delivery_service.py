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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog_item import CatalogItem
from app.models.catalog_media import CatalogMedia
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.catalog_retrieval_service import CatalogRetrievalItem
from app.services.storage.base import StorageProvider

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.65
_SPAM_WINDOW_MINUTES = 30
_SIGNED_URL_EXPIRY = 3600  # 1 hour — enough for a link-based provider (Meta) to fetch


# ── Decision result ───────────────────────────────────────────────────────────

@dataclass
class MediaDeliveryDecision:
    should_send: bool
    reason: str
    item_id: uuid.UUID | None = None
    media_id: uuid.UUID | None = None
    # Storage key (not a public URL) — resolved by whichever OutboundProvider
    # ends up delivering it (whatsapp-voice-groq-elevenlabs-prd.md fixed this
    # to go through the provider registry instead of a Meta-only hardcode).
    file_key: str | None = None
    mime_type: str | None = None
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
        file_key=media.file_key,
        mime_type=media.mime_type,
        media_url=url,
        caption=caption,
    )


def deliver_catalog_media_image(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    decision: MediaDeliveryDecision,
    agent_id: uuid.UUID,
) -> ConversationMessage | None:
    """
    Send the catalog image via WhatsApp and persist a ConversationMessage record.

    Delivery itself goes through the provider-agnostic
    ``messaging.deliver_media_message`` — whatsapp-voice-groq-elevenlabs-prd.md
    fixed this from a Meta-only hardcode (which silently never worked for the
    Evolution API channels that are actually in production use).

    Returns the created ConversationMessage, or None if delivery was skipped.
    Never raises — all errors are caught, logged, and recorded in metadata_json.
    """
    if not decision.should_send:
        return None

    # Persist message record first (outbound, content_type=image). media_url
    # is the real storage key — same convention as inbound image/audio.
    media_msg = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_type="agent",
        agent_id=agent_id,
        content=f"[Imagem: {decision.caption or 'Produto do catálogo'}]",
        content_type="image",
        media_url=decision.file_key,
        metadata_json={
            "catalog_media_delivery": {
                "attempted": True,
                "sent": False,
                "item_id": str(decision.item_id),
                "media_id": str(decision.media_id),
                "caption": decision.caption,
                "reason": decision.reason,
            }
        },
    )
    db.add(media_msg)
    db.flush()

    try:
        from app.services.messaging import deliver_media_message  # noqa: PLC0415

        deliver_media_message(
            db, media_msg, conversation,
            storage_key=decision.file_key, mime_type=decision.mime_type or "image/jpeg",
            caption=decision.caption,
        )
    except Exception as exc:
        _record_delivery_failure(db, media_msg, decision, exc)
        return media_msg

    delivery_status = (media_msg.metadata_json or {}).get("delivery", {}).get("status")
    logger.info(
        "catalog_media_delivery attempted item_id=%s media_id=%s status=%s conversation_id=%s",
        decision.item_id, decision.media_id, delivery_status, conversation.id,
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
        meta = msg.metadata_json or {}
        catalog_meta = meta.get("catalog_media_delivery", {})
        # "sent" lives on the provider-agnostic delivery block now (set by
        # whichever OutboundProvider handled it), not on catalog_media_delivery
        # itself — that key only ever tracks attempt bookkeeping.
        was_sent = meta.get("delivery", {}).get("status") == "sent"
        if catalog_meta.get("media_id") == media_id_str and was_sent:
            return True
    return False


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
