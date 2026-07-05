"""
Service de App Review — lógica de envio, templates e logs.
Provisório e isolado do fluxo multi-tenant do Wenzap.
"""

import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.whatsapp_review_log import WhatsappReviewLog
from app.models.whatsapp_review_message import WhatsappReviewMessage
from app.models.whatsapp_review_template import WhatsappReviewTemplate
from app.services.meta_review.client import MetaApiError, create_message_template, send_text_message

logger = logging.getLogger(__name__)

_MAX_MESSAGE_LENGTH = 4096


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise ValueError("Número de telefone inválido: nenhum dígito encontrado.")
    if len(digits) < 8:
        raise ValueError("Número de telefone muito curto. Inclua o código do país.")
    return digits


def _save_log(
    db: Session,
    event_type: str,
    status: str,
    summary: str | None = None,
    raw_payload: dict | None = None,
) -> None:
    log = WhatsappReviewLog(
        event_type=event_type,
        status=status,
        summary=summary,
        raw_payload=raw_payload,
    )
    db.add(log)
    db.commit()


def get_env_status() -> dict:
    """Retorna booleanos indicando presença de cada ENV sensível. Nunca retorna valores."""
    return {
        "has_access_token": bool(settings.meta_review_access_token),
        "has_waba_id": bool(settings.meta_review_waba_id),
        "has_phone_number_id": bool(settings.meta_review_phone_number_id),
        "has_webhook_verify_token": bool(settings.meta_review_webhook_verify_token),
        "has_admin_emails": bool(settings.meta_review_admin_emails),
        "phone_number_id_masked": (
            f"****{settings.meta_review_phone_number_id[-4:]}"
            if len(settings.meta_review_phone_number_id) >= 4
            else "****"
        ),
        "waba_id_masked": (
            f"****{settings.meta_review_waba_id[-5:]}"
            if len(settings.meta_review_waba_id) >= 5
            else "****"
        ),
        "webhook_signature_required": settings.meta_review_webhook_signature_required,
    }


def send_test_message(db: Session, to: str, message: str) -> dict:
    to = _normalize_phone(to)

    if not message.strip():
        raise ValueError("Mensagem não pode ser vazia.")
    if len(message) > _MAX_MESSAGE_LENGTH:
        raise ValueError(f"Mensagem excede {_MAX_MESSAGE_LENGTH} caracteres.")

    if not settings.meta_review_access_token:
        raise ValueError("META_REVIEW_ACCESS_TOKEN não configurado.")
    if not settings.meta_review_phone_number_id:
        raise ValueError("META_REVIEW_PHONE_NUMBER_ID não configurado.")

    record = WhatsappReviewMessage(
        direction="outbound",
        message_type="text",
        body=message,
        status="queued",
    )
    db.add(record)
    db.flush()

    try:
        result = send_text_message(to=to, body=message)
        record.meta_message_id = result.get("message_id")
        record.status = "sent"
        record.raw_payload = result.get("raw")
        db.commit()

        _save_log(
            db,
            event_type="send_message",
            status="success",
            summary=f"Mensagem enviada para {to}. message_id={record.meta_message_id}",
        )

        return {
            "success": True,
            "message_id": record.meta_message_id,
            "to": to,
            "status": "sent",
        }

    except MetaApiError as exc:
        record.status = "failed"
        record.error_code = exc.code
        record.error_message = exc.message
        db.commit()

        _save_log(
            db,
            event_type="send_message",
            status="error",
            summary=f"Falha ao enviar para {to}: [{exc.code}] {exc.message}",
        )

        return {
            "success": False,
            "error": {"code": exc.code, "message": exc.message},
        }

    except Exception as exc:
        record.status = "failed"
        record.error_message = str(exc)
        db.commit()

        logger.exception("meta_review send_test_message unexpected error to=%s", to)
        _save_log(db, event_type="send_message", status="error", summary=str(exc))

        return {
            "success": False,
            "error": {"code": "internal", "message": str(exc)},
        }


def create_template(db: Session, name: str, language: str, category: str, body: str) -> dict:
    if not re.match(r"^[a-z0-9_]+$", name):
        raise ValueError("Nome do template deve conter apenas letras minúsculas, números e underscore.")

    valid_categories = {"UTILITY", "MARKETING", "AUTHENTICATION"}
    if category not in valid_categories:
        raise ValueError(f"Categoria inválida. Use: {', '.join(valid_categories)}")

    if not settings.meta_review_access_token:
        raise ValueError("META_REVIEW_ACCESS_TOKEN não configurado.")
    if not settings.meta_review_waba_id:
        raise ValueError("META_REVIEW_WABA_ID não configurado.")

    record = WhatsappReviewTemplate(
        name=name,
        language=language,
        category=category,
        body=body,
        status="draft",
    )
    db.add(record)
    db.flush()

    try:
        result = create_message_template(name=name, language=language, category=category, body=body)

        record.meta_template_id = str(result.get("id", ""))
        record.status = result.get("status", "pending")
        record.raw_response = result
        db.commit()

        _save_log(
            db,
            event_type="create_template",
            status="success",
            summary=f"Template '{name}' criado. meta_id={record.meta_template_id} status={record.status}",
        )

        return {
            "success": True,
            "template_id": str(record.id),
            "meta_template_id": record.meta_template_id,
            "status": record.status,
        }

    except MetaApiError as exc:
        record.status = "error"
        record.raw_response = {"error_code": exc.code, "error_message": exc.message}
        db.commit()

        _save_log(
            db,
            event_type="create_template",
            status="error",
            summary=f"Falha ao criar template '{name}': [{exc.code}] {exc.message}",
        )

        return {
            "success": False,
            "error": {"code": exc.code, "message": exc.message},
        }

    except Exception as exc:
        record.status = "error"
        db.commit()

        logger.exception("meta_review create_template unexpected error name=%s", name)
        _save_log(db, event_type="create_template", status="error", summary=str(exc))

        return {
            "success": False,
            "error": {"code": "internal", "message": str(exc)},
        }


def list_logs(db: Session, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(WhatsappReviewLog).order_by(WhatsappReviewLog.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": str(r.id),
            "event_type": r.event_type,
            "status": r.status,
            "summary": r.summary,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def list_messages(db: Session, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(WhatsappReviewMessage).order_by(WhatsappReviewMessage.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": str(r.id),
            "direction": r.direction,
            "body": r.body,
            "status": r.status,
            "meta_message_id": r.meta_message_id,
            "error_code": r.error_code,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def list_templates(db: Session) -> list[dict]:
    rows = db.scalars(
        select(WhatsappReviewTemplate).order_by(WhatsappReviewTemplate.created_at.desc())
    ).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "language": r.language,
            "category": r.category,
            "body": r.body,
            "status": r.status,
            "meta_template_id": r.meta_template_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
