"""
Endpoints admin para App Review da Meta — WhatsApp Cloud API.
Acesso restrito: usuário autenticado + role owner + e-mail em META_REVIEW_ADMIN_EMAILS.
Provisório e isolado do fluxo multi-tenant.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.services import workspace_service
from app.services.meta_review import service as meta_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/meta-review/whatsapp", tags=["meta-review"])


def _require_meta_review_access(
    current_user: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> User:
    role = workspace_service.get_current_member_role(db, workspace.id, current_user.id)
    logger.info("META_REVIEW_AUTH email=%s role=%r role_str=%r", current_user.email, role, str(role))

    if str(role) != "owner":
        logger.warning("META_REVIEW_AUTH denied: role check failed (role=%r)", role)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")

    allowed = settings.meta_review_admin_emails_list
    logger.info("META_REVIEW_AUTH allowed_emails=%r", allowed)
    if allowed and current_user.email.lower() not in allowed:
        logger.warning("META_REVIEW_AUTH denied: email %r not in allowed list", current_user.email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado.")

    return current_user


class SendTestMessageRequest(BaseModel):
    to: str
    message: str = "Olá! Esta é uma mensagem de teste enviada pelo Wenzap via API oficial do WhatsApp."


class CreateTemplateRequest(BaseModel):
    name: str = "confirmacao_atendimento"
    language: str = "pt_BR"
    category: str = "UTILITY"
    body: str = "Olá, seu atendimento foi iniciado pelo Wenzap. Em breve nossa equipe continuará a conversa por aqui."


@router.get("/status")
def get_status(_: User = Depends(_require_meta_review_access)):
    return meta_service.get_env_status()


@router.post("/send-test")
def send_test_message(
    body: SendTestMessageRequest,
    _: User = Depends(_require_meta_review_access),
    db: Session = Depends(get_db),
):
    try:
        return meta_service.send_test_message(db=db, to=body.to, message=body.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/templates")
def create_template(
    body: CreateTemplateRequest,
    _: User = Depends(_require_meta_review_access),
    db: Session = Depends(get_db),
):
    try:
        return meta_service.create_template(
            db=db,
            name=body.name,
            language=body.language,
            category=body.category,
            body=body.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/templates")
def get_templates(
    _: User = Depends(_require_meta_review_access),
    db: Session = Depends(get_db),
):
    return meta_service.list_templates(db)


@router.get("/messages")
def get_messages(
    _: User = Depends(_require_meta_review_access),
    db: Session = Depends(get_db),
):
    return meta_service.list_messages(db)


@router.get("/logs")
def get_logs(
    _: User = Depends(_require_meta_review_access),
    db: Session = Depends(get_db),
):
    return meta_service.list_logs(db)
