"""
Tests for Phase 5.1.3 — Conversations API.

Covers:
  1. ConversationCreate (contact_id / contact_name / agent_id / channel_type validation)
  2. Inline contact creation via contact_name
  3. Listing (default excludes archived, status filter, skip/limit, tenant isolation)
  4. GET (existing, cross-tenant 404, not found 404)
  5. PATCH (status, ai_enabled, agent_id, assigned_user_id, null-clears, cross-tenant 404)
  6. RBAC (viewer read-only, member/admin/owner write)
  7. Tenant isolation
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


def _seed_contact(db: Session, workspace: Workspace, name: str = "Test Contact") -> Contact:
    c = Contact(workspace_id=workspace.id, name=name)
    db.add(c)
    db.flush()
    return c


def _seed_agent(db: Session, workspace: Workspace, name: str = "Test Agent") -> Agent:
    agent = Agent(workspace_id=workspace.id, name=name)
    db.add(agent)
    db.flush()
    return agent


def _seed_conversation(
    db: Session, workspace: Workspace, contact: Contact, **kwargs
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        status=kwargs.pop("status", "open"),
        channel_type=kwargs.pop("channel_type", "internal"),
        ai_enabled=kwargs.pop("ai_enabled", True),
        **kwargs,
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


# ══════════════════════════════════════════════════════════════════════════════
# 1. CREATE — contact_id
# ══════════════════════════════════════════════════════════════════════════════


def test_create_conversation_with_contact_id(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    db.commit()

    r = client_a.post("/conversations", json={"contact_id": str(contact.id)})
    assert r.status_code == 201
    body = r.json()
    assert body["contact_id"] == str(contact.id)
    assert body["status"] == "open"
    assert body["channel_type"] == "internal"
    assert body["ai_enabled"] is True
    assert body["workspace_id"] == str(workspace_a.id)
    assert body["last_message_at"] is None


def test_create_conversation_with_agent_id(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    agent = _seed_agent(db, workspace_a)
    db.commit()

    r = client_a.post(
        "/conversations",
        json={"contact_id": str(contact.id), "agent_id": str(agent.id)},
    )
    assert r.status_code == 201
    assert r.json()["agent_id"] == str(agent.id)


def test_create_conversation_channel_type(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    db.commit()

    r = client_a.post(
        "/conversations",
        json={"contact_id": str(contact.id), "channel_type": "web_widget"},
    )
    assert r.status_code == 201
    assert r.json()["channel_type"] == "web_widget"


def test_create_conversation_invalid_channel_type(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    db.commit()

    r = client_a.post(
        "/conversations",
        json={"contact_id": str(contact.id), "channel_type": "telegram"},
    )
    assert r.status_code == 422


def test_create_conversation_no_contact_422(db: Session, client_a):
    r = client_a.post("/conversations", json={})
    assert r.status_code == 422


def test_create_conversation_both_contact_fields_422(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    db.commit()

    r = client_a.post(
        "/conversations",
        json={"contact_id": str(contact.id), "contact_name": "Extra"},
    )
    assert r.status_code == 422


def test_create_conversation_contact_other_workspace_404(
    db: Session, client_a, workspace_b: Workspace
):
    contact = _seed_contact(db, workspace_b, name="WS-B Contact")
    db.commit()

    r = client_a.post("/conversations", json={"contact_id": str(contact.id)})
    assert r.status_code == 404


def test_create_conversation_agent_other_workspace_404(
    db: Session, client_a, workspace_a: Workspace, workspace_b: Workspace
):
    contact = _seed_contact(db, workspace_a)
    agent = _seed_agent(db, workspace_b)
    db.commit()

    r = client_a.post(
        "/conversations",
        json={"contact_id": str(contact.id), "agent_id": str(agent.id)},
    )
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 2. CREATE — inline contact via contact_name
# ══════════════════════════════════════════════════════════════════════════════


def test_create_conversation_with_contact_name_creates_contact(
    db: Session, client_a, workspace_a: Workspace
):
    r = client_a.post("/conversations", json={"contact_name": "Ana Souza"})
    assert r.status_code == 201
    body = r.json()
    # A contact_id must be returned (the inline-created contact).
    assert body["contact_id"] is not None

    # The contact must exist in the DB scoped to workspace_a.
    contact = db.scalar(
        __import__("sqlalchemy", fromlist=["select"]).select(Contact).where(
            Contact.id == uuid.UUID(body["contact_id"]),
            Contact.workspace_id == workspace_a.id,
        )
    )
    assert contact is not None
    assert contact.name == "Ana Souza"


def test_create_conversation_contact_name_stripped(
    db: Session, client_a, workspace_a: Workspace
):
    # Leading/trailing spaces in contact_name must be stripped before saving.
    r = client_a.post("/conversations", json={"contact_name": "  Ana Souza  "})
    assert r.status_code == 201
    contact_id = r.json()["contact_id"]
    from sqlalchemy import select as _select
    contact = db.scalar(
        _select(Contact).where(Contact.id == uuid.UUID(contact_id))
    )
    assert contact is not None
    assert contact.name == "Ana Souza"


def test_create_conversation_contact_name_blank_422(db: Session, client_a):
    r = client_a.post("/conversations", json={"contact_name": "   "})
    assert r.status_code == 422


def test_create_conversation_contact_name_empty_422(db: Session, client_a):
    r = client_a.post("/conversations", json={"contact_name": ""})
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# 3. LIST
# ══════════════════════════════════════════════════════════════════════════════


def test_list_conversations_empty(db: Session, client_a):
    r = client_a.get("/conversations")
    assert r.status_code == 200
    assert r.json() == []


def test_list_conversations_returns_own_workspace(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    _seed_conversation(db, workspace_a, contact)
    _seed_conversation(db, workspace_a, contact, status="pending")
    db.commit()

    r = client_a.get("/conversations")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_conversations_excludes_archived_by_default(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    _seed_conversation(db, workspace_a, contact, status="open")
    _seed_conversation(db, workspace_a, contact, status="archived")
    db.commit()

    r = client_a.get("/conversations")
    statuses = [c["status"] for c in r.json()]
    assert "archived" not in statuses
    assert len(statuses) == 1


def test_list_conversations_status_archived_returns_archived(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    _seed_conversation(db, workspace_a, contact, status="open")
    _seed_conversation(db, workspace_a, contact, status="archived")
    db.commit()

    r = client_a.get("/conversations?status=archived")
    statuses = [c["status"] for c in r.json()]
    assert all(s == "archived" for s in statuses)
    assert len(statuses) == 1


def test_list_conversations_filter_by_status(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    _seed_conversation(db, workspace_a, contact, status="open")
    _seed_conversation(db, workspace_a, contact, status="resolved")
    _seed_conversation(db, workspace_a, contact, status="pending")
    db.commit()

    r = client_a.get("/conversations?status=resolved")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["status"] == "resolved"


def test_list_conversations_skip_limit(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    for _ in range(5):
        _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.get("/conversations?skip=2&limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_conversations_limit_capped_at_100(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    for _ in range(3):
        _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.get("/conversations?limit=500")
    assert r.status_code == 200
    assert len(r.json()) <= 100


# ══════════════════════════════════════════════════════════════════════════════
# 4. GET
# ══════════════════════════════════════════════════════════════════════════════


def test_get_conversation_returns_correct_data(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a, name="Fetch Me")
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.get(f"/conversations/{conv.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(conv.id)
    assert body["contact_id"] == str(contact.id)


def test_get_conversation_not_found(db: Session, client_a):
    r = client_a.get(f"/conversations/{uuid.uuid4()}")
    assert r.status_code == 404


def test_get_conversation_cross_tenant_404(
    db: Session, user_a: User, workspace_a: Workspace, workspace_b: Workspace
):
    contact = _seed_contact(db, workspace_b)
    conv = _seed_conversation(db, workspace_b, contact)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.get(f"/conversations/{conv.id}")
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 5. UPDATE
# ══════════════════════════════════════════════════════════════════════════════


def test_update_conversation_status(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"status": "resolved"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


def test_update_conversation_invalid_status_422(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"status": "deleted"})
    assert r.status_code == 422


def test_update_conversation_ai_enabled(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"ai_enabled": False})
    assert r.status_code == 200
    assert r.json()["ai_enabled"] is False


def test_update_conversation_ai_enabled_null_422(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"ai_enabled": None})
    assert r.status_code == 422


def test_update_conversation_set_agent(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    agent = _seed_agent(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"agent_id": str(agent.id)})
    assert r.status_code == 200
    assert r.json()["agent_id"] == str(agent.id)


def test_update_conversation_clear_agent_with_null(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    agent = _seed_agent(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact, agent_id=agent.id)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"agent_id": None})
    assert r.status_code == 200
    assert r.json()["agent_id"] is None


def test_update_conversation_agent_other_workspace_404(
    db: Session, client_a, workspace_a: Workspace, workspace_b: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    agent_b = _seed_agent(db, workspace_b)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"agent_id": str(agent_b.id)})
    assert r.status_code == 404


def test_update_conversation_set_assigned_user(
    db: Session, client_a, workspace_a: Workspace
):
    member = _make_member(db, workspace_a, MemberRole.member)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(
        f"/conversations/{conv.id}", json={"assigned_user_id": str(member.id)}
    )
    assert r.status_code == 200
    assert r.json()["assigned_user_id"] == str(member.id)


def test_update_conversation_clear_assigned_user_with_null(
    db: Session, client_a, workspace_a: Workspace
):
    member = _make_member(db, workspace_a, MemberRole.member)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact, assigned_user_id=member.id)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"assigned_user_id": None})
    assert r.status_code == 200
    assert r.json()["assigned_user_id"] is None


def test_update_conversation_assigned_user_not_member_422(
    db: Session, client_a, workspace_a: Workspace
):
    # Create a user that is NOT a member of workspace_a.
    stranger = _make_user(db, f"stranger-{uuid.uuid4().hex[:6]}@test.com", "Stranger")
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(
        f"/conversations/{conv.id}", json={"assigned_user_id": str(stranger.id)}
    )
    assert r.status_code == 422


def test_update_conversation_not_found(db: Session, client_a):
    r = client_a.patch(f"/conversations/{uuid.uuid4()}", json={"status": "resolved"})
    assert r.status_code == 404


def test_update_conversation_cross_tenant_404(
    db: Session, user_a: User, workspace_a: Workspace, workspace_b: Workspace
):
    contact = _seed_contact(db, workspace_b)
    conv = _seed_conversation(db, workspace_b, contact)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.patch(f"/conversations/{conv.id}", json={"status": "resolved"})
    assert r.status_code == 404


def test_update_conversation_absent_fields_not_changed(
    db: Session, client_a, workspace_a: Workspace
):
    agent = _seed_agent(db, workspace_a)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact, agent_id=agent.id)
    db.commit()

    # Only updating status; agent_id must remain.
    r = client_a.patch(f"/conversations/{conv.id}", json={"status": "pending"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["agent_id"] == str(agent.id)


# ══════════════════════════════════════════════════════════════════════════════
# 6. RBAC
# ══════════════════════════════════════════════════════════════════════════════


def test_viewer_can_list_conversations(
    db: Session, workspace_a: Workspace, user_a: User
):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    contact = _seed_contact(db, workspace_a)
    _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.get("/conversations")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_viewer_can_get_conversation(
    db: Session, workspace_a: Workspace, user_a: User
):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.get(f"/conversations/{conv.id}")
    assert r.status_code == 200


def test_viewer_cannot_create_conversation(
    db: Session, workspace_a: Workspace, user_a: User
):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    contact = _seed_contact(db, workspace_a)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.post("/conversations", json={"contact_id": str(contact.id)})
    assert r.status_code == 403


def test_viewer_cannot_update_conversation(
    db: Session, workspace_a: Workspace, user_a: User
):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.patch(f"/conversations/{conv.id}", json={"status": "resolved"})
    assert r.status_code == 403


@pytest.mark.parametrize("role", [MemberRole.member, MemberRole.admin, MemberRole.owner])
def test_write_roles_can_create_conversation(
    db: Session, workspace_a: Workspace, user_a: User, role: MemberRole
):
    user = _make_member(db, workspace_a, role)
    contact = _seed_contact(db, workspace_a)
    db.commit()

    with _make_client(db, user, workspace_a) as client:
        r = client.post("/conversations", json={"contact_id": str(contact.id)})
    assert r.status_code == 201


@pytest.mark.parametrize("role", [MemberRole.member, MemberRole.admin, MemberRole.owner])
def test_write_roles_can_update_conversation(
    db: Session, workspace_a: Workspace, user_a: User, role: MemberRole
):
    user = _make_member(db, workspace_a, role)
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, user, workspace_a) as client:
        r = client.patch(f"/conversations/{conv.id}", json={"status": "pending"})
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 7. TENANT ISOLATION
# ══════════════════════════════════════════════════════════════════════════════


def test_list_conversations_excludes_other_workspace(
    db: Session,
    user_a: User, workspace_a: Workspace,
    user_b: User, workspace_b: Workspace,
):
    contact_a = _seed_contact(db, workspace_a, name="WS-A Contact")
    contact_b = _seed_contact(db, workspace_b, name="WS-B Contact")
    _seed_conversation(db, workspace_a, contact_a)
    _seed_conversation(db, workspace_b, contact_b)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r_a = client.get("/conversations")

    with _make_client(db, user_b, workspace_b) as client:
        r_b = client.get("/conversations")

    assert len(r_a.json()) == 1
    assert len(r_b.json()) == 1
    assert r_a.json()[0]["workspace_id"] == str(workspace_a.id)
    assert r_b.json()[0]["workspace_id"] == str(workspace_b.id)


def test_get_conversation_cross_tenant_isolation(
    db: Session,
    user_a: User, workspace_a: Workspace,
    workspace_b: Workspace,
):
    contact_b = _seed_contact(db, workspace_b)
    conv_b = _seed_conversation(db, workspace_b, contact_b)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.get(f"/conversations/{conv_b.id}")
    assert r.status_code == 404


def test_patch_conversation_cross_tenant_isolation(
    db: Session,
    user_a: User, workspace_a: Workspace,
    workspace_b: Workspace,
):
    contact_b = _seed_contact(db, workspace_b)
    conv_b = _seed_conversation(db, workspace_b, contact_b)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.patch(f"/conversations/{conv_b.id}", json={"status": "resolved"})
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 8. CONTACT NAME — 5.2.1 regression
# ══════════════════════════════════════════════════════════════════════════════


def test_list_conversations_includes_contact_name(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a, name="Maria Clara")
    _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.get("/conversations")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["contact_name"] == "Maria Clara"


def test_get_conversation_includes_contact_name(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a, name="Pedro Alves")
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.get(f"/conversations/{conv.id}")
    assert r.status_code == 200
    assert r.json()["contact_name"] == "Pedro Alves"


def test_create_with_contact_id_response_includes_contact_name(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a, name="Carla Dias")
    db.commit()

    r = client_a.post("/conversations", json={"contact_id": str(contact.id)})
    assert r.status_code == 201
    assert r.json()["contact_name"] == "Carla Dias"


def test_create_with_contact_name_response_includes_contact_name(
    db: Session, client_a, workspace_a: Workspace
):
    r = client_a.post("/conversations", json={"contact_name": "Inline User"})
    assert r.status_code == 201
    assert r.json()["contact_name"] == "Inline User"


def test_conversation_without_contact_returns_null_contact_name(
    db: Session, client_a, workspace_a: Workspace
):
    # Seed a conversation directly with contact_id=None (simulates a deleted contact).
    conv = Conversation(
        workspace_id=workspace_a.id,
        contact_id=None,
        status="open",
        channel_type="internal",
        ai_enabled=True,
    )
    db.add(conv)
    db.commit()

    r_list = client_a.get("/conversations")
    r_get = client_a.get(f"/conversations/{conv.id}")
    assert r_list.status_code == 200
    assert r_get.status_code == 200
    # No contact linked — contact_name must be null.
    found = next((c for c in r_list.json() if c["id"] == str(conv.id)), None)
    assert found is not None
    assert found["contact_name"] is None
    assert r_get.json()["contact_name"] is None


def test_update_conversation_response_includes_contact_name(
    db: Session, client_a, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a, name="Lucas Souza")
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    r = client_a.patch(f"/conversations/{conv.id}", json={"status": "pending"})
    assert r.status_code == 200
    assert r.json()["contact_name"] == "Lucas Souza"
