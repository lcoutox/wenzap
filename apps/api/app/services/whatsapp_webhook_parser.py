"""
Parser for Meta/WhatsApp Cloud API webhook payloads.

Pure functions — no DB access, no side effects.
Extracts inbound text messages from the nested Meta payload structure.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppContact:
    wa_id: str
    profile_name: str | None = None


@dataclass
class WhatsAppInboundMessage:
    phone_number_id: str
    wamid: str
    from_wa_id: str
    timestamp: int | None
    text_body: str
    contact: WhatsAppContact | None


def parse_inbound_text_messages(payload: object) -> list[WhatsAppInboundMessage]:
    """
    Extract all inbound text messages from a Meta webhook payload.

    Iterates all entries and changes. Ignores status updates, unsupported
    message types, and malformed structures — never raises.
    """
    if not isinstance(payload, dict):
        return []

    results: list[WhatsAppInboundMessage] = []

    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) or []:
            if not isinstance(change, dict):
                continue
            if change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue

            messages = _extract_text_messages(value)
            results.extend(messages)

    return results


def is_status_update(payload: object) -> bool:
    """
    Return True if the payload contains only status updates (no inbound messages).

    Used to skip processing without logging an error.
    """
    if not isinstance(payload, dict):
        return False

    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue
            if "statuses" in value and "messages" not in value:
                return True

    return False


# ── Private helpers ────────────────────────────────────────────────────────────


def _extract_text_messages(value: dict) -> list[WhatsAppInboundMessage]:
    """Extract text messages from a single change value block."""
    results: list[WhatsAppInboundMessage] = []

    metadata = value.get("metadata") or {}
    phone_number_id: str | None = (
        metadata.get("phone_number_id") if isinstance(metadata, dict) else None
    )
    if not phone_number_id:
        return results

    # Build a wa_id → profile_name map from the contacts array.
    contact_map: dict[str, str | None] = {}
    for c in value.get("contacts", []) or []:
        if not isinstance(c, dict):
            continue
        wa_id = c.get("wa_id")
        if not wa_id:
            continue
        profile = c.get("profile") or {}
        name = profile.get("name") if isinstance(profile, dict) else None
        contact_map[wa_id] = name

    for message in value.get("messages", []) or []:
        if not isinstance(message, dict):
            continue

        msg_type = message.get("type")
        if msg_type != "text":
            logger.info(
                "whatsapp_parser skipping unsupported message type=%s wamid=%s",
                msg_type,
                message.get("id"),
            )
            continue

        wamid = message.get("id")
        from_wa_id = message.get("from")
        if not wamid or not from_wa_id:
            logger.info("whatsapp_parser skipping message missing id or from field")
            continue

        text_block = message.get("text") or {}
        text_body = text_block.get("body", "") if isinstance(text_block, dict) else ""
        if not text_body:
            logger.info("whatsapp_parser skipping text message with empty body wamid=%s", wamid)
            continue

        timestamp_raw = message.get("timestamp")
        try:
            timestamp = int(timestamp_raw) if timestamp_raw is not None else None
        except (ValueError, TypeError):
            timestamp = None

        profile_name = contact_map.get(from_wa_id)
        contact = WhatsAppContact(wa_id=from_wa_id, profile_name=profile_name)

        results.append(
            WhatsAppInboundMessage(
                phone_number_id=phone_number_id,
                wamid=wamid,
                from_wa_id=from_wa_id,
                timestamp=timestamp,
                text_body=text_body,
                contact=contact,
            )
        )

    return results
