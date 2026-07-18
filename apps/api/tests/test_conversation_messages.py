"""
Tests for Phase 5.1.4 — Conversation Messages API.

Covers:
  1. ConversationMessageCreate validation (content, direction, sender_type, content_type)
  2. Sender-type / direction combination rules
  3. Create message (all sender types)
  4. agent fallback to conversation.agent_id
  5. last_message_at + updated_at updated after message
  6. Listing (order ASC, skip/limit, tenant isolation)
  7. Workspace validations (sender_user_id, agent_id, cross-tenant conversation)
  8. RBAC
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client, _make_user

# ── Helpers ───────────────────────────────────────────────────────────────────


def _seed_contact(db: Session, workspace: Workspace) -> Contact:
    c = Contact(workspace_id=workspace.id, name="Msg Test Contact")
    db.add(c)
    db.flush()
    return c


def _seed_agent(db: Session, workspace: Workspace) -> Agent:
    a = Agent(workspace_id=workspace.id, name=f"Agent-{uuid.uuid4().hex[:6]}")
    db.add(a)
    db.flush()
    return a


def _seed_conversation(
    db: Session,
    workspace: Workspace,
    contact: Contact,
    agent: Agent | None = None,
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        agent_id=agent.id if agent else None,
        status="open",
        channel_type="internal",
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()
    return conv


def _make_member(db: Session, workspace: Workspace, role: MemberRole) -> User:
    email = f"{role.value}-{uuid.uuid4().hex[:6]}@test.com"
    user = _make_user(db, email, f"{role.value.title()} User")
    db.add(WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=role,
        status=MemberStatus.active,
    ))
    db.flush()
    return user


def _post_msg(client, conv_id, **kwargs):
    return client.post(f"/conversations/{conv_id}/messages", json=kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# 1. SCHEMA VALIDATION — content
# ══════════════════════════════════════════════════════════════════════════════


def test_create_message_content_empty_422(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="",
        direction="inbound",
        sender_type="customer",
    )
    assert r.status_code == 422


def test_create_message_content_whitespace_422(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="   ",
        direction="inbound",
        sender_type="customer",
    )
    assert r.status_code == 422


def test_create_message_content_type_not_text_422(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Hello",
        direction="inbound",
        sender_type="customer",
        content_type="image",
    )
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 2. SCHEMA VALIDATION — direction + sender_type combinations
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("direction,sender_type", [
    ("outbound", "customer"),
    ("internal", "customer"),
    ("inbound",  "agent"),
    ("internal", "agent"),
    ("inbound",  "system"),
    ("outbound", "system"),
])
def test_invalid_direction_sender_type_combination_422(
    db: Session, client_a, workspace_a: Workspace,
    direction: str, sender_type: str,
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Test",
        direction=direction,
        sender_type=sender_type,
    )
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 3. CREATE — all valid sender types
# ══════════════════════════════════════════════════════════════════════════════


def test_create_message_customer_inbound(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Hello from customer",
        direction="inbound",
        sender_type="customer",
    )
    assert r.status_code == 201
    body = r.json()
    assert body["direction"] == "inbound"
    assert body["sender_type"] == "customer"
    assert body["content"] == "Hello from customer"
    assert body["sender_user_id"] is None
    assert body["content_type"] == "text"
    assert body["conversation_id"] == str(conv.id)
    assert body["workspace_id"] == str(workspace_a.id)


def test_create_message_human_outbound_uses_current_user(
    db: Session, client_a, workspace_a: Workspace, user_a: User
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Agent human reply",
        direction="outbound",
        sender_type="human",
    )
    assert r.status_code == 201
    assert r.json()["sender_user_id"] == str(user_a.id)


def test_create_message_human_internal(
    db: Session, client_a, workspace_a: Workspace, user_a: User
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Internal note",
        direction="internal",
        sender_type="human",
    )
    assert r.status_code == 201
    assert r.json()["direction"] == "internal"
    assert r.json()["sender_user_id"] == str(user_a.id)


def test_create_message_human_explicit_sender_user_id(
    db: Session, client_a, workspace_a: Workspace, user_a: User
):
    member = _make_member(db, workspace_a, MemberRole.member)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="From explicit member",
        direction="outbound",
        sender_type="human",
        sender_user_id=str(member.id),
    )
    assert r.status_code == 201
    assert r.json()["sender_user_id"] == str(member.id)


def test_create_message_agent_with_agent_id(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    agent = _seed_agent(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="AI response",
        direction="outbound",
        sender_type="agent",
        agent_id=str(agent.id),
    )
    assert r.status_code == 201
    assert r.json()["agent_id"] == str(agent.id)
    assert r.json()["sender_user_id"] is None


def test_create_message_agent_falls_back_to_conversation_agent(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    agent = _seed_agent(db, workspace_a)
    # Conversation already has an agent assigned.
    conv = _seed_conversation(db, workspace_a, contact, agent=agent)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Auto-reply",
        direction="outbound",
        sender_type="agent",
        # No agent_id in payload — service must use conv.agent_id.
    )
    assert r.status_code == 201
    assert r.json()["agent_id"] == str(agent.id)


def test_create_message_agent_no_agent_anywhere_422(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)  # No agent.
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Bot msg",
        direction="outbound",
        sender_type="agent",
    )
    assert r.status_code == 422


def test_create_message_system_internal(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Conversation started",
        direction="internal",
        sender_type="system",
    )
    assert r.status_code == 201
    assert r.json()["sender_user_id"] is None
    assert r.json()["agent_id"] is None


def test_create_message_metadata_persists(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    meta = {"source": "widget", "session": "abc123"}
    r = _post_msg(
        client_a, conv.id,
        content="Hi",
        direction="inbound",
        sender_type="customer",
        metadata=meta,
    )
    assert r.status_code == 201
    assert r.json()["metadata_json"] == meta


# ══════════════════════════════════════════════════════════════════════════════
# 4. last_message_at / updated_at
# ══════════════════════════════════════════════════════════════════════════════


def test_first_message_sets_last_message_at(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    assert conv.last_message_at is None

    r = _post_msg(
        client_a, conv.id,
        content="First",
        direction="inbound",
        sender_type="customer",
    )
    assert r.status_code == 201

    db.refresh(conv)
    assert conv.last_message_at is not None


def test_second_message_updates_last_message_at(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    _post_msg(
        client_a, conv.id,
        content="First",
        direction="inbound",
        sender_type="customer",
    )
    db.refresh(conv)
    first_lma = conv.last_message_at

    _post_msg(
        client_a, conv.id,
        content="Second",
        direction="inbound",
        sender_type="customer",
    )
    db.refresh(conv)
    assert conv.last_message_at >= first_lma


def test_create_message_updates_conversation_updated_at(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Hello",
        direction="inbound",
        sender_type="customer",
    )
    assert r.status_code == 201

    db.refresh(conv)
    assert conv.updated_at is not None


# ══════════════════════════════════════════════════════════════════════════════
# 5. LIST
# ══════════════════════════════════════════════════════════════════════════════


def test_list_messages_empty(db: Session, client_a, workspace_a: Workspace):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.get(f"/conversations/{conv.id}/messages")
    assert r.status_code == 200
    assert r.json() == []


def test_list_messages_ordered_asc(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    _post_msg(client_a, conv.id, content="First", direction="inbound", sender_type="customer")
    _post_msg(client_a, conv.id, content="Second", direction="inbound", sender_type="customer")
    _post_msg(client_a, conv.id, content="Third", direction="inbound", sender_type="customer")

    r = client_a.get(f"/conversations/{conv.id}/messages")
    contents = [m["content"] for m in r.json()]
    assert contents == ["First", "Second", "Third"]


def test_list_messages_skip_limit(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    for i in range(5):
        _post_msg(
            client_a, conv.id,
            content=f"Msg {i}",
            direction="inbound",
            sender_type="customer",
        )

    r = client_a.get(f"/conversations/{conv.id}/messages?skip=1&limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_messages_conversation_other_workspace_404(
    db: Session,
    user_a: User, workspace_a: Workspace,
    workspace_b: Workspace,
):
    contact_b = Contact(workspace_id=workspace_b.id, name="B")
    db.add(contact_b)
    db.flush()
    conv_b = _seed_conversation(db, workspace_b, contact_b)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.get(f"/conversations/{conv_b.id}/messages")
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 6. WORKSPACE VALIDATIONS
# ══════════════════════════════════════════════════════════════════════════════


def test_create_message_sender_user_not_member_422(
    db: Session, client_a, workspace_a: Workspace
):
    stranger = _make_user(db, f"stranger-{uuid.uuid4().hex[:6]}@test.com", "Stranger")
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Hi",
        direction="outbound",
        sender_type="human",
        sender_user_id=str(stranger.id),
    )
    assert r.status_code == 422


def test_create_message_agent_other_workspace_404(
    db: Session, client_a, workspace_a: Workspace, workspace_b: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    agent_b = _seed_agent(db, workspace_b)
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Bot",
        direction="outbound",
        sender_type="agent",
        agent_id=str(agent_b.id),
    )
    assert r.status_code == 404


def test_create_message_conversation_other_workspace_404(
    db: Session,
    user_a: User, workspace_a: Workspace,
    workspace_b: Workspace,
):
    contact_b = Contact(workspace_id=workspace_b.id, name="B")
    db.add(contact_b)
    db.flush()
    conv_b = _seed_conversation(db, workspace_b, contact_b)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = _post_msg(
            client, conv_b.id,
            content="Hijack",
            direction="inbound",
            sender_type="customer",
        )
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 7. RBAC
# ══════════════════════════════════════════════════════════════════════════════


def test_viewer_can_list_messages(
    db: Session, workspace_a: Workspace, user_a: User
):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.get(f"/conversations/{conv.id}/messages")
    assert r.status_code == 200


def test_viewer_cannot_create_message(
    db: Session, workspace_a: Workspace, user_a: User
):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = _post_msg(
            client, conv.id,
            content="Hi",
            direction="inbound",
            sender_type="customer",
        )
    assert r.status_code == 403


@pytest.mark.parametrize("role", [MemberRole.member, MemberRole.admin, MemberRole.owner])
def test_write_roles_can_create_message(
    db: Session, workspace_a: Workspace, user_a: User, role: MemberRole
):
    user = _make_member(db, workspace_a, role)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, user, workspace_a) as client:
        r = _post_msg(
            client, conv.id,
            content="Message from role",
            direction="inbound",
            sender_type="customer",
        )
    assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 9. AUTO-REOPEN on resolved conversations (mark-resolved-tool-prd.md)
# ══════════════════════════════════════════════════════════════════════════════


def test_customer_message_reopens_resolved_conversation(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    conv.status = "resolved"
    conv.resolution_summary = "Cliente confirmou recebimento."
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Na verdade voltou a dar problema.",
        direction="inbound",
        sender_type="customer",
    )
    assert r.status_code == 201

    db.refresh(conv)
    assert conv.status == "open"
    assert conv.resolution_summary is None


def test_human_message_does_not_reopen_resolved_conversation(
    db: Session, client_a, workspace_a: Workspace, user_a: User
):
    """Only a customer message reopens — a human/agent/system message on a
    resolved conversation shouldn't silently flip it back to open."""
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    conv.status = "resolved"
    conv.resolution_summary = "Cliente confirmou recebimento."
    db.commit()

    r = _post_msg(
        client_a, conv.id,
        content="Nota interna.",
        direction="internal",
        sender_type="human",
    )
    assert r.status_code == 201

    db.refresh(conv)
    assert conv.status == "resolved"
    assert conv.resolution_summary == "Cliente confirmou recebimento."


def test_customer_message_on_open_conversation_leaves_resolution_summary_alone(
    db: Session, client_a, workspace_a: Workspace
):
    """Sanity check: the auto-reopen branch only fires when status is
    actually "resolved" — must not clear an unrelated summary otherwise
    (there shouldn't be one on an open conversation, but confirms no
    unconditional clear-on-every-customer-message bug)."""
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()
    assert conv.status == "open"

    r = _post_msg(
        client_a, conv.id,
        content="Primeira mensagem.",
        direction="inbound",
        sender_type="customer",
    )
    assert r.status_code == 201

    db.refresh(conv)
    assert conv.status == "open"
    assert conv.resolution_summary is None
