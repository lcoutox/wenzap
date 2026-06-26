"""
Parser for Meta/WhatsApp Cloud API webhook payloads.

Pure functions — no DB access, no side effects.
Extracts inbound text messages and status updates from Meta payload structures.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppStatusUpdate:
    phone_number_id: str | None
    wamid: str
    status: str
    timestamp: int | None
    recipient_id: str | None
    conversation_id: str | None
    conversation_origin_type: str | None
    pricing_category: str | None
    pricing_model: str | None
    billable: bool | None
    error_code: str | None
    error_title: str | None
    error_message: str | None


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


def parse_status_updates(payload: object) -> list[WhatsAppStatusUpdate]:
    """
    Extract all status updates from a Meta webhook payload.

    Iterates all entries and changes. Ignores entries without a valid id.
    Never raises — malformed structures are skipped silently.
    """
    if not isinstance(payload, dict):
        return []

    results: list[WhatsAppStatusUpdate] = []

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

            metadata = value.get("metadata") or {}
            phone_number_id = (
                metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            )

            for status_obj in value.get("statuses", []) or []:
                if not isinstance(status_obj, dict):
                    continue
                wamid = status_obj.get("id")
                if not wamid:
                    continue

                status_str = status_obj.get("status") or ""
                timestamp_raw = status_obj.get("timestamp")
                try:
                    timestamp = int(timestamp_raw) if timestamp_raw is not None else None
                except (ValueError, TypeError):
                    timestamp = None

                conv_block = status_obj.get("conversation") or {}
                conv_id = conv_block.get("id") if isinstance(conv_block, dict) else None
                origin = (
                    conv_block.get("origin") if isinstance(conv_block, dict) else None
                )
                conv_origin_type = (
                    origin.get("type") if isinstance(origin, dict) else None
                )

                pricing_block = status_obj.get("pricing") or {}
                pricing_category: str | None = None
                pricing_model: str | None = None
                billable: bool | None = None
                if isinstance(pricing_block, dict):
                    pricing_category = pricing_block.get("category")
                    pricing_model = pricing_block.get("pricing_model")
                    raw_billable = pricing_block.get("billable")
                    billable = bool(raw_billable) if raw_billable is not None else None

                errors = status_obj.get("errors") or []
                error_code: str | None = None
                error_title: str | None = None
                error_message_str: str | None = None
                if isinstance(errors, list) and errors:
                    first_error = errors[0]
                    if isinstance(first_error, dict):
                        raw_code = first_error.get("code")
                        error_code = str(raw_code) if raw_code is not None else None
                        error_title = first_error.get("title")
                        error_message_str = first_error.get("message")

                results.append(
                    WhatsAppStatusUpdate(
                        phone_number_id=phone_number_id,
                        wamid=wamid,
                        status=status_str,
                        timestamp=timestamp,
                        recipient_id=status_obj.get("recipient_id"),
                        conversation_id=conv_id,
                        conversation_origin_type=conv_origin_type,
                        pricing_category=pricing_category,
                        pricing_model=pricing_model,
                        billable=billable,
                        error_code=error_code,
                        error_title=error_title,
                        error_message=error_message_str,
                    )
                )

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
