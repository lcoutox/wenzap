"""
WhatsApp status update processing service — Phase 6.4-A.

Processes delivery status updates received from Meta webhook and updates
the corresponding outbound ConversationMessage in the Inbox.

Design notes:
- process_status_update() never raises. All errors are caught and logged.
- Status progression is enforced to avoid visual regressions (e.g. read → delivered).
- failed always overrides any prior status (terminal error state).
- Unknown statuses are stored in last_status_raw but do not overwrite delivery.status.
- Timestamps from Meta are converted to ISO UTC; last_status_at always uses now().
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation_message import ConversationMessage
from app.services.whatsapp_webhook_parser import WhatsAppStatusUpdate

logger = logging.getLogger(__name__)

# Rank used to prevent status regression.
# failed is handled separately as a terminal override.
_STATUS_RANK: dict[str, int] = {
    "sent": 1,
    "delivered": 2,
    "read": 3,
}


# ── Public API ─────────────────────────────────────────────────────────────────


def process_status_update(
    db: Session,
    update: WhatsAppStatusUpdate,
) -> ConversationMessage | None:
    """
    Find the outbound ConversationMessage matching update.wamid and update
    its metadata_json.delivery with the new status information.

    Returns the updated message, or None if not found or on error.
    Never raises.
    """
    try:
        return _process(db, update)
    except Exception:
        logger.exception(
            "whatsapp_status unexpected error wamid=%s status=%s",
            update.wamid,
            update.status,
        )
        return None


def should_update_status(current: str | None, incoming: str) -> bool:
    """
    Return True if incoming status should overwrite the current delivery status.

    Rules:
    - failed always overwrites (terminal error).
    - Known statuses only advance (sent < delivered < read).
    - Unknown statuses never overwrite.
    """
    if incoming == "failed":
        return True
    incoming_rank = _STATUS_RANK.get(incoming, 0)
    if incoming_rank == 0:
        return False
    current_rank = _STATUS_RANK.get(current or "", 0)
    return incoming_rank > current_rank


# ── Private ────────────────────────────────────────────────────────────────────


def _process(
    db: Session,
    update: WhatsAppStatusUpdate,
) -> ConversationMessage | None:
    message = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.external_message_id == update.wamid,
            ConversationMessage.direction == "outbound",
        )
    )

    if message is None:
        logger.info(
            "whatsapp_status message not found wamid=%s status=%s",
            update.wamid,
            update.status,
        )
        return None

    now = datetime.now(timezone.utc)
    existing = message.metadata_json or {}
    delivery = dict(existing.get("delivery") or {})

    # Convert Meta timestamp to ISO UTC string, if provided.
    meta_ts: str | None = None
    if update.timestamp is not None:
        try:
            meta_ts = datetime.fromtimestamp(
                update.timestamp, tz=timezone.utc
            ).isoformat()
        except (OSError, OverflowError, ValueError):
            meta_ts = None

    # Always record the last received status and when it arrived.
    delivery["last_status_raw"] = update.status
    delivery["last_status_at"] = now.isoformat()

    # Advance delivery.status only when appropriate.
    if should_update_status(delivery.get("status"), update.status):
        delivery["status"] = update.status

    # Status-specific timestamps (only set when Meta provides a timestamp).
    if meta_ts:
        if update.status == "sent":
            delivery.setdefault("sent_at", meta_ts)
        elif update.status == "delivered":
            delivery["delivered_at"] = meta_ts
        elif update.status == "read":
            delivery["read_at"] = meta_ts
        elif update.status == "failed":
            delivery["failed_at"] = meta_ts

    # Conversation metadata (only set when present in the update).
    if update.conversation_id:
        delivery["meta_conversation_id"] = update.conversation_id
    if update.conversation_origin_type:
        delivery["conversation_origin_type"] = update.conversation_origin_type

    # Pricing (only set when at least one field is present).
    if (
        update.pricing_category is not None
        or update.pricing_model is not None
        or update.billable is not None
    ):
        delivery["pricing"] = {
            "billable": update.billable,
            "pricing_model": update.pricing_model,
            "category": update.pricing_category,
        }

    # Error details (only for failed status).
    if update.status == "failed":
        delivery["error_code"] = update.error_code
        delivery["error_title"] = update.error_title
        delivery["error_message"] = update.error_message

    message.metadata_json = {**existing, "delivery": delivery}
    db.commit()

    logger.info(
        "whatsapp_status updated message_id=%s wamid=%s status=%s",
        message.id,
        update.wamid,
        update.status,
    )
    return message
