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
class WhatsAppHistoryMessage:
    """One message from a `history` webhook field batch — whatsapp-coexistence-prd.md."""

    phone_number_id: str
    wamid: str
    from_number: str
    to_number: str
    thread_wa_id: str
    timestamp: int | None
    text_body: str
    message_type: str
    direction: str  # "inbound" | "outbound" — derived from from_number vs the business number
    phase: int | None
    chunk_order: int | None
    progress: int | None


@dataclass
class WhatsAppStateSyncContact:
    """One contact add/remove event from `smb_app_state_sync` — whatsapp-coexistence-prd.md."""

    phone_number_id: str
    action: str  # "add" | "remove"
    contact_phone: str
    full_name: str | None
    first_name: str | None
    timestamp: int | None


@dataclass
class WhatsAppMessageEcho:
    """One message the business owner sent via their own app — whatsapp-coexistence-prd.md."""

    phone_number_id: str
    wamid: str
    from_number: str
    to_number: str
    timestamp: int | None
    text_body: str
    message_type: str


@dataclass
class WhatsAppInboundMessage:
    phone_number_id: str
    wamid: str
    from_wa_id: str
    timestamp: int | None
    text_body: str
    contact: WhatsAppContact | None
    # "text" | "image" | "audio". Defaults to "text" so every existing
    # construction site keeps working unchanged. See
    # conversation-image-upload-prd.md, whatsapp-voice-groq-elevenlabs-prd.md.
    message_type: str = "text"
    # Meta's own media asset id (distinct from wamid) — needed to download
    # image/audio via the Graph API. None for text and for the Evolution
    # parser, which re-derives media by wamid instead. See
    # meta-cloud-api-parity-prd.md.
    media_id: str | None = None
    media_mime_type: str | None = None


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
                origin = conv_block.get("origin") if isinstance(conv_block, dict) else None
                conv_origin_type = origin.get("type") if isinstance(origin, dict) else None

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


def parse_history_messages(payload: object) -> list[WhatsAppHistoryMessage]:
    """
    Extract all messages from a `history` webhook field payload — sent when a
    business connects via WhatsApp Coexistence and shares message history.
    whatsapp-coexistence-prd.md.

    Never raises — malformed structures are skipped silently, same contract
    as the other parsers in this module.
    """
    if not isinstance(payload, dict):
        return []

    results: list[WhatsAppHistoryMessage] = []

    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) or []:
            if not isinstance(change, dict) or change.get("field") != "history":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata") or {}
            metadata_is_dict = isinstance(metadata, dict)
            phone_number_id = metadata.get("phone_number_id") if metadata_is_dict else None
            business_number = metadata.get("display_phone_number") if metadata_is_dict else None
            if not phone_number_id:
                continue

            for batch in value.get("history", []) or []:
                if not isinstance(batch, dict):
                    continue
                batch_meta = batch.get("metadata") or {}
                batch_meta_is_dict = isinstance(batch_meta, dict)
                phase = _safe_int(batch_meta.get("phase")) if batch_meta_is_dict else None
                chunk_order = (
                    _safe_int(batch_meta.get("chunk_order")) if batch_meta_is_dict else None
                )
                progress = (
                    _safe_int(batch_meta.get("progress")) if batch_meta_is_dict else None
                )

                for thread in batch.get("threads", []) or []:
                    if not isinstance(thread, dict):
                        continue
                    thread_wa_id = thread.get("id")
                    if not thread_wa_id:
                        continue

                    for message in thread.get("messages", []) or []:
                        if not isinstance(message, dict):
                            continue
                        wamid = message.get("id")
                        from_number = message.get("from")
                        to_number = message.get("to")
                        if not wamid or not from_number or not to_number:
                            logger.info(
                                "whatsapp_parser skipping history message missing id/from/to"
                            )
                            continue

                        msg_type = message.get("type") or "text"
                        text_body = _extract_generic_text_body(message, msg_type)
                        direction = (
                            "outbound"
                            if business_number and _same_number(from_number, business_number)
                            else "inbound"
                        )

                        results.append(
                            WhatsAppHistoryMessage(
                                phone_number_id=phone_number_id,
                                wamid=wamid,
                                from_number=from_number,
                                to_number=to_number,
                                thread_wa_id=thread_wa_id,
                                timestamp=_safe_int(message.get("timestamp")),
                                text_body=text_body,
                                message_type=msg_type,
                                direction=direction,
                                phase=phase,
                                chunk_order=chunk_order,
                                progress=progress,
                            )
                        )

    return results


def parse_state_sync_contacts(payload: object) -> list[WhatsAppStateSyncContact]:
    """
    Extract contact add/remove events from a `smb_app_state_sync` webhook
    field payload. whatsapp-coexistence-prd.md.
    """
    if not isinstance(payload, dict):
        return []

    results: list[WhatsAppStateSyncContact] = []

    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) or []:
            if not isinstance(change, dict) or change.get("field") != "smb_app_state_sync":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata") or {}
            phone_number_id = (
                metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            )
            if not phone_number_id:
                continue

            for item in value.get("state_sync", []) or []:
                if not isinstance(item, dict) or item.get("type") != "contact":
                    continue
                action = item.get("action")
                if action not in ("add", "remove"):
                    continue
                contact = item.get("contact") or {}
                if not isinstance(contact, dict):
                    continue
                contact_phone = contact.get("phone_number")
                if not contact_phone:
                    continue

                item_metadata = item.get("metadata") or {}
                timestamp = (
                    _safe_int(item_metadata.get("timestamp"))
                    if isinstance(item_metadata, dict)
                    else None
                )

                results.append(
                    WhatsAppStateSyncContact(
                        phone_number_id=phone_number_id,
                        action=action,
                        contact_phone=contact_phone,
                        full_name=contact.get("full_name"),
                        first_name=contact.get("first_name"),
                        timestamp=timestamp,
                    )
                )

    return results


def parse_message_echoes(payload: object) -> list[WhatsAppMessageEcho]:
    """
    Extract messages the business owner sent via their own WhatsApp Business
    app from a `smb_message_echoes` webhook field payload.
    whatsapp-coexistence-prd.md.
    """
    if not isinstance(payload, dict):
        return []

    results: list[WhatsAppMessageEcho] = []

    for entry in payload.get("entry", []) or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes", []) or []:
            if not isinstance(change, dict) or change.get("field") != "smb_message_echoes":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                continue

            metadata = value.get("metadata") or {}
            phone_number_id = (
                metadata.get("phone_number_id") if isinstance(metadata, dict) else None
            )
            if not phone_number_id:
                continue

            for message in value.get("message_echoes", []) or []:
                if not isinstance(message, dict):
                    continue
                wamid = message.get("id")
                from_number = message.get("from")
                to_number = message.get("to")
                if not wamid or not from_number or not to_number:
                    logger.info("whatsapp_parser skipping echo message missing id/from/to")
                    continue

                msg_type = message.get("type") or "text"
                text_body = _extract_generic_text_body(message, msg_type)

                results.append(
                    WhatsAppMessageEcho(
                        phone_number_id=phone_number_id,
                        wamid=wamid,
                        from_number=from_number,
                        to_number=to_number,
                        timestamp=_safe_int(message.get("timestamp")),
                        text_body=text_body,
                        message_type=msg_type,
                    )
                )

    return results


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
        is_image = msg_type == "image"
        is_audio = msg_type == "audio"
        if msg_type != "text" and not is_image and not is_audio:
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

        media_id: str | None = None
        media_mime_type: str | None = None
        text_body = ""

        if is_image or is_audio:
            media_block = message.get(msg_type) or {}
            if not isinstance(media_block, dict) or not media_block.get("id"):
                logger.info(
                    "whatsapp_parser skipping %s message missing media object wamid=%s",
                    msg_type,
                    wamid,
                )
                continue
            media_id = media_block.get("id")
            media_mime_type = media_block.get("mime_type")
            # Only images can carry a caption — an empty one is still valid
            # (matches the Evolution parser). Audio never has a body.
            if is_image:
                text_body = media_block.get("caption") or ""
        else:
            text_block = message.get("text") or {}
            text_body = text_block.get("body", "") if isinstance(text_block, dict) else ""
            if not text_body:
                logger.info(
                    "whatsapp_parser skipping text message with empty body wamid=%s", wamid
                )
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
                message_type="image" if is_image else "audio" if is_audio else "text",
                media_id=media_id,
                media_mime_type=media_mime_type,
            )
        )

    return results


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _same_number(a: str, b: str) -> bool:
    """Compare two phone-number-ish strings ignoring formatting (spaces, +, -)."""

    def _digits(s: str) -> str:
        return "".join(ch for ch in s if ch.isdigit())

    return _digits(a) == _digits(b)


def _extract_generic_text_body(message: dict, msg_type: str) -> str:
    """
    Extract a display-safe text body for a coexistence history/echo message.

    Meta's docs for `history`/`smb_message_echoes` don't specify the exact
    shape of non-text message contents (just `"<TYPE>": {<CONTENTS>}`) — to
    avoid guessing at a shape and either crashing or silently corrupting
    content, only "text" is fully extracted. Everything else becomes a
    labeled placeholder so the message still shows up instead of vanishing.
    See "Fora de escopo" in whatsapp-coexistence-prd.md.
    """
    if msg_type == "text":
        text_block = message.get("text") or {}
        if isinstance(text_block, dict):
            return text_block.get("body", "") or ""
        return ""
    return f"[mensagem de {msg_type} — histórico/echo do WhatsApp Business App]"
