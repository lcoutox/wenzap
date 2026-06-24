import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate

_MAX_LIMIT = 100


def list_contacts(
    db: Session,
    workspace_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[Contact]:
    effective_limit = min(limit, _MAX_LIMIT)
    return list(
        db.scalars(
            select(Contact)
            .where(Contact.workspace_id == workspace_id)
            .order_by(Contact.created_at.desc())
            .offset(skip)
            .limit(effective_limit)
        ).all()
    )


def create_contact(
    db: Session,
    workspace_id: uuid.UUID,
    data: ContactCreate,
) -> Contact:
    contact = Contact(
        workspace_id=workspace_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
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
            detail="Contact not found.",
        )
    return contact


def update_contact(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    data: ContactUpdate,
) -> Contact:
    contact = get_contact_or_404(db, workspace_id, contact_id)

    # Only update fields that were explicitly included in the request.
    # model_fields_set contains the names of fields present in the payload.
    if "name" in data.model_fields_set:
        contact.name = data.name  # type: ignore[assignment]  # null rejected by validator
    if "email" in data.model_fields_set:
        contact.email = data.email
    if "phone" in data.model_fields_set:
        contact.phone = data.phone
    if "external_id" in data.model_fields_set:
        contact.external_id = data.external_id
    if "metadata" in data.model_fields_set:
        contact.metadata_json = data.metadata

    contact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(contact)
    return contact
