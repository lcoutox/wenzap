"""
Public Stripe webhook receiver. Configure in the Stripe Dashboard as:
  POST https://api.wenzap.com.br/webhooks/stripe

Signature verification (STRIPE_WEBHOOK_SECRET) is the only authentication —
this endpoint intentionally has no session/workspace auth dependency.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.stripe_service import StripeService, get_stripe_service
from app.services.stripe_webhook_handler import StripeWebhookHandler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stripe-webhooks"])


@router.post("/webhooks/stripe")
async def handle_stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> dict:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cabeçalho stripe-signature ausente.")

    event = stripe_service.verify_webhook_signature(payload, sig_header)
    if not event:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assinatura inválida.")

    handler = StripeWebhookHandler(stripe_service)
    try:
        handler.process_event(event, db)
    except Exception:
        # Log and still 200 — the event is idempotency-keyed, so Stripe's retry
        # will simply re-attempt the same (still-failing) processing rather than
        # cause duplicate side effects. We don't want to lose the delivery.
        logger.exception("Error processing Stripe webhook event %s", event.get("id"))

    return {"status": "ok"}
