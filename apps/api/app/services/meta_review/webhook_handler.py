"""
Handler de webhooks Meta para App Review.
Provisório e isolado do fluxo multi-tenant.
Nunca aciona agente, auto-reply ou Inbox real nesta fase.
"""

import hashlib
import hmac
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.models.whatsapp_review_contact import WhatsappReviewContact
from app.models.whatsapp_review_conversation import WhatsappReviewConversation
from app.models.whatsapp_review_log import WhatsappReviewLog
from app.models.whatsapp_review_message import WhatsappReviewMessage

logger = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    Valida X-Hub-Signature-256 usando META_APP_SECRET.
    Retorna True se assinatura válida ou se verificação desabilitada.
    Apenas para webhook POST — GET de verificação não usa assinatura.
    """
    if not settings.meta_review_webhook_signature_required:
        return True

    if not signature_header:
        return False

    if not settings.meta_app_secret:
        logger.warning("meta_review_webhook signature required but META_APP_SECRET not set")
        return False

    expected = "sha256=" + hmac.new(
        settings.meta_app_secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)


def _get_or_create_contact(db: Session, wa_id: str, profile_name: str | None) -> WhatsappReviewContact:
    from sqlalchemy import select
    contact = db.scalar(
        select(WhatsappReviewContact).where(WhatsappReviewContact.wa_id == wa_id)
    )
    if contact:
        if profile_name and contact.profile_name != profile_name:
            contact.profile_name = profile_name
            db.commit()
        return contact

    contact = WhatsappReviewContact(
        wa_id=wa_id,
        phone_e164=f"+{wa_id}",
        profile_name=profile_name,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _get_or_create_conversation(db: Session, contact_id) -> WhatsappReviewConversation:
    from sqlalchemy import select
    conv = db.scalar(
        select(WhatsappReviewConversation)
        .where(
            WhatsappReviewConversation.contact_id == contact_id,
            WhatsappReviewConversation.status == "open",
        )
    )
    if conv:
        return conv

    conv = WhatsappReviewConversation(contact_id=contact_id, status="open")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def process_webhook(db: Session, payload: dict) -> None:
    """
    Processa payload de webhook Meta.
    Persiste log raw, extrai mensagens inbound e status updates.
    Responde 200 rapidamente — nunca lança exceção.
    """
    try:
        _save_log(db, "webhook", "received", "Webhook recebido", payload)
        _process_entries(db, payload)
    except Exception:
        logger.exception("meta_review process_webhook unexpected error")


def _process_entries(db: Session, payload: dict) -> None:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            _process_messages(db, value)
            _process_statuses(db, value)


def _process_messages(db: Session, value: dict) -> None:
    contacts_meta = {c["wa_id"]: c.get("profile", {}).get("name") for c in value.get("contacts", [])}

    for msg in value.get("messages", []):
        try:
            wa_id = msg.get("from", "")
            wamid = msg.get("id", "")
            body = msg.get("text", {}).get("body", "") if msg.get("type") == "text" else ""

            # Idempotência
            from sqlalchemy import select
            existing = db.scalar(
                select(WhatsappReviewMessage).where(WhatsappReviewMessage.meta_message_id == wamid)
            )
            if existing:
                continue

            contact = _get_or_create_contact(db, wa_id, contacts_meta.get(wa_id))
            conv = _get_or_create_conversation(db, contact.id)

            record = WhatsappReviewMessage(
                conversation_id=conv.id,
                contact_id=contact.id,
                meta_message_id=wamid,
                direction="inbound",
                message_type=msg.get("type", "text"),
                body=body,
                status="received",
                raw_payload=msg,
            )
            db.add(record)
            db.commit()

            _save_log(db, "webhook", "received", f"Mensagem inbound de {wa_id}: {body[:80]}")
        except Exception:
            logger.exception("meta_review _process_messages error msg=%s", msg.get("id"))


def _process_statuses(db: Session, value: dict) -> None:
    for status_obj in value.get("statuses", []):
        try:
            wamid = status_obj.get("id", "")
            new_status = status_obj.get("status", "")

            from sqlalchemy import select
            msg = db.scalar(
                select(WhatsappReviewMessage).where(WhatsappReviewMessage.meta_message_id == wamid)
            )
            if msg:
                msg.status = new_status
                db.commit()
        except Exception:
            logger.exception("meta_review _process_statuses error wamid=%s", status_obj.get("id"))


def _save_log(db: Session, event_type: str, status: str, summary: str | None, raw_payload: dict | None = None) -> None:
    try:
        log = WhatsappReviewLog(
            event_type=event_type,
            status=status,
            summary=summary,
            raw_payload=raw_payload,
        )
        db.add(log)
        db.commit()
    except Exception:
        logger.exception("meta_review _save_log error")
