"""
WhatsApp Cloud API webhook endpoints.

GET  /webhooks/whatsapp/meta  — Meta webhook verification (hub challenge)
POST /webhooks/whatsapp/meta  — Inbound payloads (messages, statuses, etc.)

Security notes:
- GET is protected by the verify token set in the Meta dashboard.
- POST currently returns 200 unconditionally — Meta requires a fast acknowledgement
  and must never receive non-200 for transient internal errors.
  TODO: validate X-Hub-Signature-256 using WHATSAPP_APP_SECRET in a future phase.
"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.whatsapp_inbound_service import process_inbound_message
from app.services.whatsapp_status_service import process_status_update
from app.services.whatsapp_webhook_parser import (
    parse_inbound_text_messages,
    parse_status_updates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks-whatsapp"])


@router.get("/meta", response_class=PlainTextResponse)
async def whatsapp_verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    """
    Meta webhook verification handshake.

    Meta sends a GET with hub.mode=subscribe, hub.verify_token, and hub.challenge.
    We must echo hub.challenge as plain text with status 200 if the token matches.
    """
    token_ok = (
        hub_mode == "subscribe"
        and hub_verify_token is not None
        and hub_verify_token == settings.whatsapp_webhook_verify_token
        and settings.whatsapp_webhook_verify_token != ""
    )

    if not token_ok:
        return PlainTextResponse("Forbidden", status_code=403)

    return PlainTextResponse(hub_challenge or "", status_code=200)


@router.post("/meta", status_code=200)
async def whatsapp_receive(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    Receive inbound WhatsApp payloads from the Meta platform.

    Always returns 200 — processing errors are logged internally and never
    exposed to Meta (which would cause unnecessary retries).
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    _log_payload_summary(body)

    try:
        for status_update in parse_status_updates(body):
            process_status_update(db, status_update)
    except Exception:
        logger.exception("whatsapp_webhook status processing error — returning 200 anyway")

    try:
        for msg in parse_inbound_text_messages(body):
            process_inbound_message(db, msg)
    except Exception:
        logger.exception("whatsapp_webhook inbound processing error — returning 200 anyway")

    return {"status": "ok"}


def _log_payload_summary(body: object) -> None:
    """Log a minimal, safe summary of the incoming Meta payload."""
    if not isinstance(body, dict):
        logger.info("whatsapp_webhook received non-dict payload type=%s", type(body).__name__)
        return

    obj = body.get("object")
    entries = body.get("entry", [])
    entry_count = len(entries) if isinstance(entries, list) else 0

    changes: list[str] = []
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                for change in entry.get("changes", []):
                    if isinstance(change, dict) and "field" in change:
                        changes.append(change["field"])

    logger.info(
        "whatsapp_webhook object=%s entries=%d fields=%s",
        obj,
        entry_count,
        changes or "none",
    )
