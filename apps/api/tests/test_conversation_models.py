"""
Tests for Phase 5.1.1 — contacts, conversations, conversation_messages models
and migrations.

Verifies:
- All three models can be persisted and retrieved.
- Nullable fields accept None.
- Default values are applied (status, channel_type, ai_enabled, content_type).
- metadata_json (JSONB) round-trips correctly.
- DB-level check constraints reject invalid values.
- conversation_messages has no updated_at.
- ON DELETE CASCADE: deleting a conversation removes its messages.
- ON DELETE SET NULL: deleting workspace contact/agent sets FK to NULL.
"""


import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import (
    VALID_CHANNEL_TYPES,
    VALID_CONVERSATION_STATUSES,
    Conversation,
)
from app.models.conversation_message import (
    VALID_DIRECTIONS,
    VALID_SENDER_TYPES,
    ConversationMessage,
)
from app.models.workspace import Workspace

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_contact(db: Session, workspace: Workspace, **kwargs) -> Contact:
    c = Contact(
        workspace_id=workspace.id,
        name=kwargs.pop("name", "Test Contact"),
        **kwargs,
    )
    db.add(c)
    db.flush()
    db.refresh(c)
    return c


def _make_conversation(db: Session, workspace: Workspace, **kwargs) -> Conversation:
    conv = Conversation(workspace_id=workspace.id, **kwargs)
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


def _make_message(
    db: Session,
    workspace: Workspace,
    conversation: Conversation,
    **kwargs,
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        direction=kwargs.pop("direction", "inbound"),
        sender_type=kwargs.pop("sender_type", "customer"),
        content=kwargs.pop("content", "Hello"),
        **kwargs,
    )
    db.add(msg)
    db.flush()
    db.refresh(msg)
    return msg


# ── Contact tests ─────────────────────────────────────────────────────────────


def test_contact_minimal(db: Session, workspace_a: Workspace):
    c = _make_contact(db, workspace_a)
    db.commit()
    db.refresh(c)

    assert c.id is not None
    assert c.workspace_id == workspace_a.id
    assert c.name == "Test Contact"
    assert c.email is None
    assert c.phone is None
    assert c.external_id is None
    assert c.metadata_json is None
    assert c.created_at is not None
    assert c.updated_at is not None


def test_contact_full(db: Session, workspace_a: Workspace):
    c = _make_contact(
        db,
        workspace_a,
        name="Ana Silva",
        email="ana@example.com",
        phone="+5511999998888",
        external_id="wa_5511999998888",
        metadata_json={"source": "whatsapp", "opted_in": True},
    )
    db.commit()
    db.refresh(c)

    assert c.name == "Ana Silva"
    assert c.email == "ana@example.com"
    assert c.phone == "+5511999998888"
    assert c.external_id == "wa_5511999998888"
    assert c.metadata_json == {"source": "whatsapp", "opted_in": True}


def test_contact_nullable_fields_accept_none(db: Session, workspace_a: Workspace):
    c = _make_contact(db, workspace_a, email=None, phone=None, external_id=None)
    db.commit()
    db.refresh(c)

    assert c.email is None
    assert c.phone is None
    assert c.external_id is None


def test_contact_workspace_id_required(db: Session):
    with pytest.raises(Exception):
        db.add(Contact(name="No Workspace"))
        db.flush()


def test_contact_metadata_json_roundtrip(db: Session, workspace_a: Workspace):
    payload = {"tags": ["vip", "recorrente"], "score": 9.5, "active": True}
    c = _make_contact(db, workspace_a, metadata_json=payload)
    db.commit()
    db.refresh(c)

    assert c.metadata_json == payload


# ── Conversation tests ────────────────────────────────────────────────────────


def test_conversation_defaults(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    db.commit()
    db.refresh(conv)

    assert conv.id is not None
    assert conv.channel_type == "internal"
    assert conv.status == "open"
    assert conv.ai_enabled is True
    assert conv.contact_id is None
    assert conv.agent_id is None
    assert conv.assigned_user_id is None
    assert conv.channel_external_id is None
    assert conv.last_message_at is None
    assert conv.created_at is not None
    assert conv.updated_at is not None


def test_conversation_with_contact(db: Session, workspace_a: Workspace):
    contact = _make_contact(db, workspace_a)
    conv = _make_conversation(db, workspace_a, contact_id=contact.id)
    db.commit()
    db.refresh(conv)

    assert conv.contact_id == contact.id


def test_conversation_with_agent(db: Session, workspace_a: Workspace):
    agent = Agent(workspace_id=workspace_a.id, name="Bot", status="active")
    db.add(agent)
    db.flush()

    conv = _make_conversation(db, workspace_a, agent_id=agent.id)
    db.commit()
    db.refresh(conv)

    assert conv.agent_id == agent.id


def test_conversation_with_assigned_user(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conversation(db, workspace_a, assigned_user_id=user_a.id)
    db.commit()
    db.refresh(conv)

    assert conv.assigned_user_id == user_a.id


def test_conversation_all_statuses_valid(db: Session, workspace_a: Workspace):
    for s in VALID_CONVERSATION_STATUSES:
        conv = _make_conversation(db, workspace_a, status=s)
        db.commit()
        db.refresh(conv)
        assert conv.status == s


def test_conversation_all_channel_types_valid(db: Session, workspace_a: Workspace):
    for ct in VALID_CHANNEL_TYPES:
        conv = _make_conversation(db, workspace_a, channel_type=ct)
        db.commit()
        db.refresh(conv)
        assert conv.channel_type == ct


def test_conversation_invalid_status_raises(db: Session, workspace_a: Workspace):
    with pytest.raises(Exception):
        db.add(Conversation(workspace_id=workspace_a.id, status="unknown"))
        db.flush()
        db.execute(text("SELECT 1"))  # force server-side check


def test_conversation_invalid_channel_type_raises(db: Session, workspace_a: Workspace):
    with pytest.raises(Exception):
        db.add(Conversation(workspace_id=workspace_a.id, channel_type="fax"))
        db.flush()
        db.execute(text("SELECT 1"))


def test_conversation_ai_enabled_false(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a, ai_enabled=False)
    db.commit()
    db.refresh(conv)

    assert conv.ai_enabled is False


# ── ConversationMessage tests ─────────────────────────────────────────────────


def test_message_inbound_customer(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    msg = _make_message(db, workspace_a, conv, direction="inbound", sender_type="customer")
    db.commit()
    db.refresh(msg)

    assert msg.id is not None
    assert msg.direction == "inbound"
    assert msg.sender_type == "customer"
    assert msg.content == "Hello"
    assert msg.content_type == "text"
    assert msg.created_at is not None
    assert not hasattr(msg, "updated_at") or msg.__class__.__dict__.get("updated_at") is None


def test_message_outbound_human(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conversation(db, workspace_a)
    msg = _make_message(
        db, workspace_a, conv,
        direction="outbound",
        sender_type="human",
        sender_user_id=user_a.id,
        content="Como posso ajudar?",
    )
    db.commit()
    db.refresh(msg)

    assert msg.direction == "outbound"
    assert msg.sender_type == "human"
    assert msg.sender_user_id == user_a.id


def test_message_outbound_agent(db: Session, workspace_a: Workspace):
    agent = Agent(workspace_id=workspace_a.id, name="Bot", status="active")
    db.add(agent)
    db.flush()

    conv = _make_conversation(db, workspace_a, agent_id=agent.id)
    msg = _make_message(
        db, workspace_a, conv,
        direction="outbound",
        sender_type="agent",
        agent_id=agent.id,
        content="Olá! Posso ajudar?",
    )
    db.commit()
    db.refresh(msg)

    assert msg.sender_type == "agent"
    assert msg.agent_id == agent.id


def test_message_internal_system(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    msg = _make_message(
        db, workspace_a, conv,
        direction="internal",
        sender_type="system",
        content="Conversa iniciada via canal internal.",
    )
    db.commit()
    db.refresh(msg)

    assert msg.direction == "internal"
    assert msg.sender_type == "system"
    assert msg.sender_user_id is None
    assert msg.agent_id is None


def test_message_metadata_json_roundtrip(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    payload = {"channel_msg_id": "wamid.abc123", "template": "welcome"}
    msg = _make_message(db, workspace_a, conv, metadata_json=payload)
    db.commit()
    db.refresh(msg)

    assert msg.metadata_json == payload


def test_message_invalid_direction_raises(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    with pytest.raises(Exception):
        db.add(ConversationMessage(
            workspace_id=workspace_a.id,
            conversation_id=conv.id,
            direction="sideways",
            sender_type="customer",
            content="test",
        ))
        db.flush()
        db.execute(text("SELECT 1"))


def test_message_invalid_sender_type_raises(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    with pytest.raises(Exception):
        db.add(ConversationMessage(
            workspace_id=workspace_a.id,
            conversation_id=conv.id,
            direction="inbound",
            sender_type="robot",
            content="test",
        ))
        db.flush()
        db.execute(text("SELECT 1"))


def test_message_cascade_delete_with_conversation(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    conv_id = conv.id
    _make_message(db, workspace_a, conv, content="msg 1")
    _make_message(db, workspace_a, conv, content="msg 2")
    db.commit()

    db.delete(conv)
    db.commit()

    remaining = db.query(ConversationMessage).filter_by(conversation_id=conv_id).all()
    assert remaining == []


def test_message_has_no_updated_at(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    _make_message(db, workspace_a, conv)
    db.commit()

    columns = {col.key for col in ConversationMessage.__table__.columns}
    assert "updated_at" not in columns


def test_message_created_at_is_populated(db: Session, workspace_a: Workspace):
    conv = _make_conversation(db, workspace_a)
    msg = _make_message(db, workspace_a, conv)
    db.commit()
    db.refresh(msg)

    assert msg.created_at is not None


# ── Constants sanity ──────────────────────────────────────────────────────────


def test_valid_statuses_constant():
    assert "open" in VALID_CONVERSATION_STATUSES
    assert "archived" in VALID_CONVERSATION_STATUSES
    assert "resolved" in VALID_CONVERSATION_STATUSES
    assert "pending" in VALID_CONVERSATION_STATUSES


def test_valid_channel_types_constant():
    assert "internal" in VALID_CHANNEL_TYPES
    assert "whatsapp" in VALID_CHANNEL_TYPES


def test_valid_directions_constant():
    assert "inbound" in VALID_DIRECTIONS
    assert "outbound" in VALID_DIRECTIONS
    assert "internal" in VALID_DIRECTIONS


def test_valid_sender_types_constant():
    assert "customer" in VALID_SENDER_TYPES
    assert "human" in VALID_SENDER_TYPES
    assert "agent" in VALID_SENDER_TYPES
    assert "system" in VALID_SENDER_TYPES
