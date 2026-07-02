import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.contact_variable import ContactVariable
from app.models.conversation import Conversation
from app.schemas.contact import (
    ContactCreate,
    ContactListOut,
    ContactUpdate,
    ContactVariableCreate,
    ContactVariableUpdate,
)

_MAX_LIMIT = 100


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise_email(email: str | None) -> str | None:
    return email.strip().lower() if email else None


def _normalise_phone(phone: str | None) -> str | None:
    return phone.strip() if phone else None


def _check_dedup(
    db: Session,
    workspace_id: uuid.UUID,
    email: str | None,
    phone: str | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if email:
        q = select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.email == email,
        )
        if exclude_id:
            q = q.where(Contact.id != exclude_id)
        if db.scalar(q):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um contato com o e-mail '{email}' neste workspace.",
            )
    if phone:
        q = select(Contact).where(
            Contact.workspace_id == workspace_id,
            Contact.phone == phone,
        )
        if exclude_id:
            q = q.where(Contact.id != exclude_id)
        if db.scalar(q):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe um contato com o telefone '{phone}' neste workspace.",
            )


# ── Contact CRUD ──────────────────────────────────────────────────────────────

def list_contacts(
    db: Session,
    workspace_id: uuid.UUID,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ContactListOut:
    effective_limit = min(limit, _MAX_LIMIT)
    base = select(Contact).where(Contact.workspace_id == workspace_id)
    if q:
        term = f"%{q.strip()}%"
        base = base.where(
            or_(
                Contact.name.ilike(term),
                Contact.email.ilike(term),
                Contact.phone.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = list(
        db.scalars(
            base.order_by(Contact.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
        ).all()
    )
    return ContactListOut(items=items, total=total, limit=effective_limit, offset=offset)


def create_contact(
    db: Session,
    workspace_id: uuid.UUID,
    data: ContactCreate,
) -> Contact:
    email = _normalise_email(data.email)
    phone = _normalise_phone(data.phone)
    _check_dedup(db, workspace_id, email, phone)
    contact = Contact(
        workspace_id=workspace_id,
        name=data.name.strip() if data.name else None,
        email=email,
        phone=phone,
        origin=data.origin,
        external_id=data.external_id,
        metadata_json=data.metadata,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def get_contact_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> Contact:
    contact = db.scalar(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.workspace_id == workspace_id,
        )
    )
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contato não encontrado.",
        )
    return contact


def update_contact(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    data: ContactUpdate,
) -> Contact:
    contact = get_contact_or_404(db, workspace_id, contact_id)
    fields = data.model_fields_set

    email = _normalise_email(data.email) if "email" in fields else contact.email
    phone = _normalise_phone(data.phone) if "phone" in fields else contact.phone

    if "email" in fields or "phone" in fields:
        _check_dedup(db, workspace_id, email, phone, exclude_id=contact_id)

    if "name" in fields:
        contact.name = data.name.strip() if data.name else contact.name
    if "email" in fields:
        contact.email = email
    if "phone" in fields:
        contact.phone = phone
    if "origin" in fields:
        contact.origin = data.origin
    if "external_id" in fields:
        contact.external_id = data.external_id
    if "metadata" in fields:
        contact.metadata_json = data.metadata

    contact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> None:
    contact = get_contact_or_404(db, workspace_id, contact_id)
    linked = db.scalar(
        select(Conversation).where(Conversation.contact_id == contact_id).limit(1)
    )
    if linked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este contato possui conversas vinculadas e não pode ser excluído.",
        )
    db.delete(contact)
    db.commit()


# ── Contact Variables ─────────────────────────────────────────────────────────

def list_variables(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> list[ContactVariable]:
    get_contact_or_404(db, workspace_id, contact_id)
    return list(
        db.scalars(
            select(ContactVariable)
            .where(ContactVariable.contact_id == contact_id)
            .order_by(ContactVariable.created_at.asc())
        ).all()
    )


def create_variable(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    data: ContactVariableCreate,
) -> ContactVariable:
    get_contact_or_404(db, workspace_id, contact_id)
    existing = db.scalar(
        select(ContactVariable).where(
            ContactVariable.contact_id == contact_id,
            ContactVariable.key == data.key,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma variável com a chave '{data.key}' neste contato.",
        )
    var = ContactVariable(
        workspace_id=workspace_id,
        contact_id=contact_id,
        key=data.key,
        value=data.value,
        source=data.source,
    )
    db.add(var)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma variável com a chave '{data.key}' neste contato.",
        )
    db.refresh(var)
    return var


def get_variable_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    variable_id: uuid.UUID,
) -> ContactVariable:
    var = db.scalar(
        select(ContactVariable).where(
            ContactVariable.id == variable_id,
            ContactVariable.contact_id == contact_id,
            ContactVariable.workspace_id == workspace_id,
        )
    )
    if not var:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Variável não encontrada.",
        )
    return var


def update_variable(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    variable_id: uuid.UUID,
    data: ContactVariableUpdate,
) -> ContactVariable:
    var = get_variable_or_404(db, workspace_id, contact_id, variable_id)
    var.value = data.value
    if data.source is not None:
        var.source = data.source
    var.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(var)
    return var


def delete_variable(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    variable_id: uuid.UUID,
) -> None:
    var = get_variable_or_404(db, workspace_id, contact_id, variable_id)
    db.delete(var)
    db.commit()
