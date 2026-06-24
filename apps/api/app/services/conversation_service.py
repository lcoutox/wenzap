import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberStatus
from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.workspace_member import WorkspaceMember
from app.schemas.contact import ContactCreate
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from app.services.contact_service import create_contact

_MAX_LIMIT = 100


def _conv_to_dict(conv: Conversation, contact_name: str | None) -> dict:
    """Serialize a Conversation ORM object to a dict, injecting contact_name."""
    return {
        "id": conv.id,
        "workspace_id": conv.workspace_id,
        "contact_id": conv.contact_id,
        "contact_name": contact_name,
        "agent_id": conv.agent_id,
        "assigned_user_id": conv.assigned_user_id,
        "channel_type": conv.channel_type,
        "channel_external_id": conv.channel_external_id,
        "status": conv.status,
        "ai_enabled": conv.ai_enabled,
        "last_message_at": conv.last_message_at,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    }


def list_conversations(
    db: Session,
    workspace_id: uuid.UUID,
    status_filter: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    effective_limit = min(limit, _MAX_LIMIT)
    q = (
        select(Conversation, Contact.name.label("contact_name"))
        .outerjoin(Contact, Conversation.contact_id == Contact.id)
        .where(Conversation.workspace_id == workspace_id)
    )
    if status_filter is not None:
        q = q.where(Conversation.status == status_filter)
    else:
        # By default, exclude archived conversations.
        q = q.where(Conversation.status != "archived")
    q = (
        q.order_by(
            Conversation.last_message_at.desc().nullslast(),
            Conversation.created_at.desc(),
        )
        .offset(skip)
        .limit(effective_limit)
    )
    rows = db.execute(q).all()
    return [_conv_to_dict(conv, contact_name) for conv, contact_name in rows]


def _require_contact(db: Session, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> Contact:
    contact = db.scalar(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.workspace_id == workspace_id,
        )
    )
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")
    return contact


def _require_agent(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    return agent


def _require_active_member(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == MemberStatus.active,
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="assigned_user_id is not an active member of this workspace.",
        )


def create_conversation(
    db: Session,
    workspace_id: uuid.UUID,
    data: ConversationCreate,
) -> dict:
    if data.contact_id is not None:
        contact = _require_contact(db, workspace_id, data.contact_id)
        contact_id = data.contact_id
        contact_name: str | None = contact.name
    else:
        # Inline contact creation from contact_name (strip to avoid leading/trailing spaces).
        inline = create_contact(
            db,
            workspace_id,
            ContactCreate(name=data.contact_name.strip()),  # type: ignore[union-attr]
        )
        contact_id = inline.id
        contact_name = inline.name

    agent_id: uuid.UUID | None = None
    if data.agent_id is not None:
        _require_agent(db, workspace_id, data.agent_id)
        agent_id = data.agent_id

    conv = Conversation(
        workspace_id=workspace_id,
        contact_id=contact_id,
        agent_id=agent_id,
        channel_type=data.channel_type,
        channel_external_id=data.channel_external_id,
        status="open",
        ai_enabled=data.ai_enabled,
        last_message_at=None,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _conv_to_dict(conv, contact_name)


def get_conversation_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Conversation:
    """Return the ORM object. Used internally by message service and update."""
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conv


def get_conversation_detail(
    db: Session,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> dict:
    """Return a dict with contact_name included. Used by the router GET endpoint."""
    row = db.execute(
        select(Conversation, Contact.name.label("contact_name"))
        .outerjoin(Contact, Conversation.contact_id == Contact.id)
        .where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    conv, contact_name = row
    return _conv_to_dict(conv, contact_name)


def update_conversation(
    db: Session,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    data: ConversationUpdate,
) -> dict:
    conv = get_conversation_or_404(db, workspace_id, conversation_id)

    if "status" in data.model_fields_set and data.status is not None:
        conv.status = data.status

    if "agent_id" in data.model_fields_set:
        if data.agent_id is not None:
            _require_agent(db, workspace_id, data.agent_id)
        conv.agent_id = data.agent_id

    if "assigned_user_id" in data.model_fields_set:
        if data.assigned_user_id is not None:
            _require_active_member(db, workspace_id, data.assigned_user_id)
        conv.assigned_user_id = data.assigned_user_id

    if "ai_enabled" in data.model_fields_set and data.ai_enabled is not None:
        conv.ai_enabled = data.ai_enabled

    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conv)

    contact_name: str | None = None
    if conv.contact_id is not None:
        contact_name = db.scalar(select(Contact.name).where(Contact.id == conv.contact_id))

    return _conv_to_dict(conv, contact_name)
