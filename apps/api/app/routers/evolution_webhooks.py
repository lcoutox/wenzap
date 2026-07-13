"""Evolution API webhook endpoint (bridge WhatsApp provider — unofficial).

POST /webhooks/whatsapp/evolution/{instance_name} — inbound messages.upsert events.

Security notes:
- The instance_name in the path resolves the channel (tenant isolation).
- Evolution includes its `apikey` in every webhook payload body. We validate
  it (constant-time compare) against the channel's stored credential
  (the same key used for outbound delivery — see EvolutionOutboundProvider).
  This is a shared-secret check, not a cryptographic signature, but requires
  no extra configuration on the Evolution side.
- Always returns 200 — processing errors are logged internally, mirroring the
  Meta webhook's never-error-the-sender behavior.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.channel_credentials_service import resolve_channel_secret
from app.services.channel_service import get_whatsapp_channel_by_instance_name
from app.services.evolution_webhook_parser import extract_apikey, parse_inbound_text_messages
from app.services.whatsapp_inbound_service import process_inbound_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp/evolution", tags=["webhooks-whatsapp"])


@router.post("/{instance_name}", status_code=200)
async def evolution_receive(
    instance_name: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    try:
        body = await request.json()
    except Exception:
        body = {}

    channel = get_whatsapp_channel_by_instance_name(db, instance_name)
    if channel is None:
        logger.info("evolution_webhook channel not found instance=%s", instance_name)
        return {"status": "ok"}

    if not _is_authorized(db, channel, body):
        logger.warning("evolution_webhook apikey mismatch instance=%s", instance_name)
        return {"status": "ok"}

    try:
        for msg in parse_inbound_text_messages(body):
            process_inbound_message(db, msg, channel=channel)
    except Exception:
        logger.exception(
            "evolution_webhook inbound processing error instance=%s — returning 200 anyway",
            instance_name,
        )

    return {"status": "ok"}


def _is_authorized(db: Session, channel, body: object) -> bool:
    ref = (channel.config_json or {}).get("api_key_ref")
    expected = resolve_channel_secret(db, channel, ref) if ref else None
    received = extract_apikey(body)
    if not expected or not received:
        return False
    return hmac.compare_digest(expected, received)
