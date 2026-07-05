"""
Webhook público da Meta para App Review.
GET  /webhooks/meta/whatsapp — verificação (hub.challenge)
POST /webhooks/meta/whatsapp — recebimento de eventos

NOTA PROVISÓRIA: endpoint separado de /webhooks/whatsapp/meta (multi-tenant).
Configurar na Meta Developer Console com este callback URL.
Não processa agente, auto-reply nem Inbox real nesta fase.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.meta_review import webhook_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/meta", tags=["meta-webhooks"])


@router.get("/whatsapp", response_class=PlainTextResponse)
async def meta_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> str:
    """
    Verificação do webhook pela Meta.
    Apenas compara hub.verify_token — sem validação de assinatura neste endpoint.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_review_webhook_verify_token:
        logger.info("meta_review_webhook verification success")
        return hub_challenge or ""

    logger.warning("meta_review_webhook verification failed mode=%s", hub_mode)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webhook verification failed")


@router.post("/whatsapp", status_code=200)
async def meta_webhook_receive(request: Request, db: Session = Depends(get_db)):
    """
    Recebe eventos da Meta (mensagens inbound, status updates).
    Valida assinatura X-Hub-Signature-256 com raw body antes de parsear JSON.
    Sempre retorna 200 rapidamente para evitar retentativas da Meta.
    """
    raw_body = await request.body()

    signature = request.headers.get("X-Hub-Signature-256")
    if not webhook_handler.verify_signature(raw_body, signature):
        logger.warning("meta_review_webhook invalid signature")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception:
        logger.warning("meta_review_webhook invalid JSON body")
        return {"status": "ok"}

    webhook_handler.process_webhook(db, payload)

    return {"status": "ok"}
