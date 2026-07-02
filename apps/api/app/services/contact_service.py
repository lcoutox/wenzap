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
    """Normalise phone to E.164 format (+<dialcode><national digits>).

    Accepted inputs (Brazilian examples that all become +5537999999999):
      (37) 99999-9999   →  strips visual chars, prepends +55
      37 99999-9999     →  same
      5537999999999     →  no +, prepends +
      +5537999999999    →  already E.164, kept as-is
      +1 (555) 123-4567 →  non-BR E.164, kept normalised

    Rules:
      1. Strip whitespace. Return None if empty.
      2. Strip all non-digit/+ chars to get a "clean" value.
      3. If already starts with "+", treat as E.164 → validate min 7 digits.
      4. If 10-11 digits (no country code), assume Brazil (+55).
      5. If 12-13 digits (country code without +), prepend "+".
      6. Reject values shorter than 7 digits after stripping.
    """
    if not phone:
        return None
    stripped = phone.strip()
    if not stripped:
        return None

    # Keep leading + if present, remove all other non-digit chars
    has_plus = stripped.startswith("+")
    digits = "".join(c for c in stripped if c.isdigit())

    if not digits:
        return None

    if has_plus:
        # Already has country code — validate minimum length (7 national digits)
        if len(digits) < 7:
            raise ValueError("Número de telefone inválido.")
        return f"+{digits}"

    # No + prefix
    if len(digits) < 7:
        raise ValueError("Número de telefone inválido.")

    if len(digits) <= 11:
        # 10-11 digits: national number only → assume Brazil +55
        return f"+55{digits}"

    if len(digits) <= 13:
        # 12-13 digits: country code already included, just prepend +
        return f"+{digits}"

    # Too many digits
    raise ValueError("Número de telefone inválido.")


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
        raw = q.strip()
        term = f"%{raw}%"
        # For phone search also try stripping non-digit chars so "(37) 9..." finds "+5537..."
        digits = "".join(c for c in raw if c.isdigit())
        digit_term = f"%{digits}%" if digits else None
        phone_clause = (
            or_(Contact.phone.ilike(term), Contact.phone.ilike(digit_term))
            if digit_term
            else Contact.phone.ilike(term)
        )
        base = base.where(
            or_(
                Contact.name.ilike(term),
                Contact.email.ilike(term),
                phone_clause,
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


def _safe_normalise_phone(phone: str | None) -> str | None:
    try:
        return _normalise_phone(phone)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


def create_contact(
    db: Session,
    workspace_id: uuid.UUID,
    data: ContactCreate,
) -> Contact:
    email = _normalise_email(data.email)
    phone = _safe_normalise_phone(data.phone)
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
    phone = _safe_normalise_phone(data.phone) if "phone" in fields else contact.phone

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
