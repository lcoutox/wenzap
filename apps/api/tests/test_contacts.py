"""
Tests for Clientes.1 — Contacts Foundation.

Covers:
  1. CREATE — minimal, full, identifier validation, deduplication
  2. LIST — pagination, search (q), tenant isolation
  3. GET — happy path, not found, cross-tenant 404
  4. UPDATE — partial update, null clear, absent fields unchanged, dedup on edit
  5. DELETE — happy path, block when conversations exist, cross-tenant 404
  6. RBAC — viewer read-only, write roles
  7. Tenant isolation — contacts scoped to workspace
  8. Contact variables — CRUD, dedup key, cross-tenant 404
  9. Conversation filter by contact_id
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
from tests.conftest import _make_client, _make_user

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_member(db: Session, workspace: Workspace, role: MemberRole) -> User:
    from app.models.workspace_member import WorkspaceMember

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


def _seed_contact(db: Session, workspace: Workspace, **kwargs) -> Contact:
    c = Contact(
        workspace_id=workspace.id,
        name=kwargs.pop("name", None),
        **kwargs,
    )
    db.add(c)
    db.flush()
    return c


def _list_items(r) -> list:
    """Extract items list from ContactListOut response."""
    return r.json()["items"]


# ══════════════════════════════════════════════════════════════════════════════
# 1. CREATE
# ══════════════════════════════════════════════════════════════════════════════


def test_create_contact_minimal(db: Session, client_a, workspace_a: Workspace):
    r = client_a.post("/contacts", json={"name": "João Silva"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "João Silva"
    assert body["email"] is None
    assert body["phone"] is None
    assert body["origin"] is None
    assert body["external_id"] is None
    assert body["metadata_json"] is None
    assert body["workspace_id"] == str(workspace_a.id)
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


def test_create_contact_full(db: Session, client_a):
    r = client_a.post("/contacts", json={
        "name": "Maria Oliveira",
        "email": "maria@example.com",
        "phone": "+5511999990000",
        "origin": "WhatsApp",
        "external_id": "wa_5511999990000",
        "metadata": {"source": "widget", "score": 8},
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Maria Oliveira"
    assert body["email"] == "maria@example.com"
    assert body["phone"] == "+5511999990000"
    assert body["origin"] == "WhatsApp"
    assert body["external_id"] == "wa_5511999990000"
    assert body["metadata_json"] == {"source": "widget", "score": 8}


def test_create_contact_with_only_email(db: Session, client_a):
    r = client_a.post("/contacts", json={"email": "only@email.com"})
    assert r.status_code == 201
    assert r.json()["email"] == "only@email.com"
    assert r.json()["name"] is None


def test_create_contact_with_only_phone(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "+5511999990001"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+5511999990001"


def test_create_contact_no_identifier_rejected(db: Session, client_a):
    r = client_a.post("/contacts", json={})
    assert r.status_code == 422


def test_create_contact_empty_strings_rejected(db: Session, client_a):
    r = client_a.post("/contacts", json={"name": "", "email": "", "phone": ""})
    assert r.status_code == 422


def test_create_contact_metadata_persists(db: Session, client_a):
    payload = {"tags": ["vip"], "score": 9.5, "active": True}
    r = client_a.post("/contacts", json={"name": "Test", "metadata": payload})
    assert r.status_code == 201
    assert r.json()["metadata_json"] == payload


# ── Deduplication ──────────────────────────────────────────────────────────────


def test_create_duplicate_email_same_workspace_rejected(db: Session, client_a, workspace_a):
    _seed_contact(db, workspace_a, email="dup@test.com", name="First")
    db.commit()

    r = client_a.post("/contacts", json={"email": "dup@test.com"})
    assert r.status_code == 409


def test_create_duplicate_email_case_insensitive(db: Session, client_a, workspace_a):
    _seed_contact(db, workspace_a, email="dup@test.com", name="First")
    db.commit()

    r = client_a.post("/contacts", json={"email": "DUP@TEST.COM"})
    assert r.status_code == 409


def test_create_duplicate_phone_same_workspace_rejected(db: Session, client_a, workspace_a):
    _seed_contact(db, workspace_a, phone="+5511999990001", name="First")
    db.commit()

    r = client_a.post("/contacts", json={"phone": "+5511999990001"})
    assert r.status_code == 409


def test_duplicate_email_other_workspace_allowed(
    db: Session, client_a, workspace_b: Workspace,
):
    _seed_contact(db, workspace_b, email="cross@ws.com", name="Other WS")
    db.commit()

    r = client_a.post("/contacts", json={"email": "cross@ws.com"})
    assert r.status_code == 201


# ══════════════════════════════════════════════════════════════════════════════
# 2. LIST
# ══════════════════════════════════════════════════════════════════════════════


def test_list_contacts_empty(db: Session, client_a):
    r = client_a.get("/contacts")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_list_contacts_returns_own_workspace(db: Session, client_a, workspace_a: Workspace):
    _seed_contact(db, workspace_a, name="Alice")
    _seed_contact(db, workspace_a, name="Bob")
    db.commit()

    r = client_a.get("/contacts")
    assert r.status_code == 200
    names = {c["name"] for c in _list_items(r)}
    assert names == {"Alice", "Bob"}
    assert r.json()["total"] == 2


def test_list_contacts_ordered_newest_first(db: Session, client_a, workspace_a: Workspace):
    c1 = _seed_contact(db, workspace_a, name="First")
    db.commit()
    db.refresh(c1)

    c2 = _seed_contact(db, workspace_a, name="Second")
    db.commit()
    db.refresh(c2)

    r = client_a.get("/contacts")
    ids = [c["id"] for c in _list_items(r)]
    assert ids[0] == str(c2.id)
    assert ids[1] == str(c1.id)


def test_list_contacts_offset_and_limit(db: Session, client_a, workspace_a: Workspace):
    for i in range(5):
        _seed_contact(db, workspace_a, name=f"Contact {i}")
    db.commit()

    r = client_a.get("/contacts?offset=2&limit=2")
    assert r.status_code == 200
    assert len(_list_items(r)) == 2
    assert r.json()["total"] == 5
    assert r.json()["offset"] == 2


def test_list_contacts_limit_over_100_rejected(db: Session, client_a):
    r = client_a.get("/contacts?limit=200")
    assert r.status_code == 422


# ── Search ─────────────────────────────────────────────────────────────────────


def test_search_by_name(db: Session, client_a, workspace_a: Workspace):
    _seed_contact(db, workspace_a, name="Pedro Alves")
    _seed_contact(db, workspace_a, name="Paula Santos")
    _seed_contact(db, workspace_a, name="Rodrigo Lima")
    db.commit()

    r = client_a.get("/contacts?q=pedro")
    assert r.status_code == 200
    items = _list_items(r)
    assert len(items) == 1
    assert items[0]["name"] == "Pedro Alves"


def test_search_by_email(db: Session, client_a, workspace_a: Workspace):
    _seed_contact(db, workspace_a, email="find@example.com", name="A")
    _seed_contact(db, workspace_a, email="other@example.com", name="B")
    db.commit()

    r = client_a.get("/contacts?q=find")
    assert r.status_code == 200
    items = _list_items(r)
    assert len(items) == 1
    assert items[0]["email"] == "find@example.com"


def test_search_by_phone(db: Session, client_a, workspace_a: Workspace):
    _seed_contact(db, workspace_a, phone="+5511991110000", name="A")
    _seed_contact(db, workspace_a, phone="+5521992220000", name="B")
    db.commit()

    r = client_a.get("/contacts?q=9111")
    assert r.status_code == 200
    items = _list_items(r)
    assert len(items) == 1
    assert items[0]["phone"] == "+5511991110000"


def test_search_no_results(db: Session, client_a, workspace_a: Workspace):
    _seed_contact(db, workspace_a, name="João")
    db.commit()

    r = client_a.get("/contacts?q=zzzzzz")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert _list_items(r) == []


# ══════════════════════════════════════════════════════════════════════════════
# 3. GET
# ══════════════════════════════════════════════════════════════════════════════


def test_get_contact_returns_correct_data(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Detail Test", email="d@test.com")
    db.commit()

    r = client_a.get(f"/contacts/{c.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(c.id)
    assert body["name"] == "Detail Test"
    assert body["email"] == "d@test.com"


def test_get_contact_not_found(db: Session, client_a):
    r = client_a.get(f"/contacts/{uuid.uuid4()}")
    assert r.status_code == 404


def test_get_contact_cross_tenant_returns_404(
    db: Session, user_a: User, workspace_a: Workspace, workspace_b: Workspace,
):
    c = _seed_contact(db, workspace_b, name="WS-B Only")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.get(f"/contacts/{c.id}")
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 4. UPDATE
# ══════════════════════════════════════════════════════════════════════════════


def test_update_contact_name(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Old Name")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_contact_email(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"email": "new@example.com"})
    assert r.status_code == 200
    assert r.json()["email"] == "new@example.com"


def test_update_contact_phone(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"phone": "+5511999991111"})
    assert r.status_code == 200
    assert r.json()["phone"] == "+5511999991111"


def test_update_contact_origin(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"origin": "Instagram"})
    assert r.status_code == 200
    assert r.json()["origin"] == "Instagram"


def test_update_contact_clears_email_with_null(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, email="old@test.com", name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"email": None})
    assert r.status_code == 200
    assert r.json()["email"] is None


def test_update_contact_clears_phone_with_null(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, phone="+5511999990000", name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"phone": None})
    assert r.status_code == 200
    assert r.json()["phone"] is None


def test_update_contact_absent_fields_not_changed(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Test", email="keep@test.com", phone="+5511999990000")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"name": "Updated"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Updated"
    assert body["email"] == "keep@test.com"
    assert body["phone"] == "+5511999990000"


def test_update_contact_dedup_email_conflict(db: Session, client_a, workspace_a: Workspace):
    _seed_contact(db, workspace_a, email="taken@test.com", name="Taken")
    c = _seed_contact(db, workspace_a, email="mine@test.com", name="Mine")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"email": "taken@test.com"})
    assert r.status_code == 409


def test_update_contact_same_email_no_conflict(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, email="same@test.com", name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"email": "same@test.com"})
    assert r.status_code == 200


def test_update_contact_not_found(db: Session, client_a):
    r = client_a.patch(f"/contacts/{uuid.uuid4()}", json={"name": "Ghost"})
    assert r.status_code == 404


def test_update_contact_cross_tenant_returns_404(
    db: Session, user_a: User, workspace_a: Workspace, workspace_b: Workspace,
):
    c = _seed_contact(db, workspace_b, name="WS-B Only")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.patch(f"/contacts/{c.id}", json={"name": "Hijacked"})
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 5. DELETE
# ══════════════════════════════════════════════════════════════════════════════


def test_delete_contact(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="To Delete")
    db.commit()

    r = client_a.delete(f"/contacts/{c.id}")
    assert r.status_code == 204

    r2 = client_a.get(f"/contacts/{c.id}")
    assert r2.status_code == 404


def test_delete_contact_not_found(db: Session, client_a):
    r = client_a.delete(f"/contacts/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_contact_cross_tenant_returns_404(
    db: Session, user_a: User, workspace_a: Workspace, workspace_b: Workspace,
):
    c = _seed_contact(db, workspace_b, name="WS-B Only")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.delete(f"/contacts/{c.id}")
    assert r.status_code == 404


def test_delete_contact_with_conversation_blocked(
    db: Session, client_a, workspace_a: Workspace, user_a: User,
):
    c = _seed_contact(db, workspace_a, name="Has Conv")
    agent = Agent(
        workspace_id=workspace_a.id,
        name="Test Agent",
        system_prompt="test",
        created_by_user_id=user_a.id,
    )
    db.add(agent)
    db.flush()
    conv = Conversation(
        workspace_id=workspace_a.id,
        contact_id=c.id,
        agent_id=agent.id,
        channel_type="web_widget",
        status="open",
    )
    db.add(conv)
    db.commit()

    r = client_a.delete(f"/contacts/{c.id}")
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════════════════════════
# 6. RBAC
# ══════════════════════════════════════════════════════════════════════════════


def test_viewer_can_list_contacts(db: Session, workspace_a: Workspace, user_a: User):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    _seed_contact(db, workspace_a, name="Visible")
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.get("/contacts")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_viewer_can_get_contact(db: Session, workspace_a: Workspace, user_a: User):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    c = _seed_contact(db, workspace_a, name="Visible")
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.get(f"/contacts/{c.id}")
    assert r.status_code == 200


def test_viewer_cannot_create_contact(db: Session, workspace_a: Workspace, user_a: User):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.post("/contacts", json={"name": "Blocked"})
    assert r.status_code == 403


def test_viewer_cannot_update_contact(db: Session, workspace_a: Workspace, user_a: User):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.patch(f"/contacts/{c.id}", json={"name": "Hacked"})
    assert r.status_code == 403


def test_viewer_cannot_delete_contact(db: Session, workspace_a: Workspace, user_a: User):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.delete(f"/contacts/{c.id}")
    assert r.status_code == 403


@pytest.mark.parametrize("role", [MemberRole.member, MemberRole.admin, MemberRole.owner])
def test_write_roles_can_create_contact(
    db: Session, workspace_a: Workspace, user_a: User, role: MemberRole,
):
    user = _make_member(db, workspace_a, role)
    db.commit()

    with _make_client(db, user, workspace_a) as client:
        r = client.post("/contacts", json={"name": f"Contact by {role.value}"})
    assert r.status_code == 201


@pytest.mark.parametrize("role", [MemberRole.member, MemberRole.admin, MemberRole.owner])
def test_write_roles_can_delete_contact(
    db: Session, workspace_a: Workspace, user_a: User, role: MemberRole,
):
    user = _make_member(db, workspace_a, role)
    c = _seed_contact(db, workspace_a, name="To Delete")
    db.commit()

    with _make_client(db, user, workspace_a) as client:
        r = client.delete(f"/contacts/{c.id}")
    assert r.status_code == 204


# ══════════════════════════════════════════════════════════════════════════════
# 7. TENANT ISOLATION
# ══════════════════════════════════════════════════════════════════════════════


def test_list_contacts_excludes_other_workspace(
    db: Session,
    user_a: User, workspace_a: Workspace,
    user_b: User, workspace_b: Workspace,
):
    _seed_contact(db, workspace_a, name="WS-A Contact")
    _seed_contact(db, workspace_b, name="WS-B Contact")
    db.commit()

    with _make_client(db, user_a, workspace_a) as ca:
        r_a = ca.get("/contacts")
    with _make_client(db, user_b, workspace_b) as cb:
        r_b = cb.get("/contacts")

    names_a = {c["name"] for c in r_a.json()["items"]}
    names_b = {c["name"] for c in r_b.json()["items"]}

    assert names_a == {"WS-A Contact"}
    assert names_b == {"WS-B Contact"}


# ══════════════════════════════════════════════════════════════════════════════
# 8. CONTACT VARIABLES
# ══════════════════════════════════════════════════════════════════════════════


def test_create_variable(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Var Test")
    db.commit()

    r = client_a.post(f"/contacts/{c.id}/variables", json={"key": "plan", "value": "premium"})
    assert r.status_code == 201
    body = r.json()
    assert body["key"] == "plan"
    assert body["value"] == "premium"
    assert body["contact_id"] == str(c.id)
    assert body["workspace_id"] == str(workspace_a.id)


def test_create_variable_with_source(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Var Test")
    db.commit()

    r = client_a.post(f"/contacts/{c.id}/variables",
                      json={"key": "segment", "value": "enterprise", "source": "crm"})
    assert r.status_code == 201
    assert r.json()["source"] == "crm"


def test_list_variables(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Var Test")
    db.commit()

    client_a.post(f"/contacts/{c.id}/variables", json={"key": "k1", "value": "v1"})
    client_a.post(f"/contacts/{c.id}/variables", json={"key": "k2", "value": "v2"})

    r = client_a.get(f"/contacts/{c.id}/variables")
    assert r.status_code == 200
    keys = {v["key"] for v in r.json()}
    assert keys == {"k1", "k2"}


def test_duplicate_variable_key_rejected(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Var Test")
    db.commit()

    client_a.post(f"/contacts/{c.id}/variables", json={"key": "plan", "value": "free"})
    r = client_a.post(f"/contacts/{c.id}/variables", json={"key": "plan", "value": "premium"})
    assert r.status_code == 409


def test_update_variable(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Var Test")
    db.commit()

    r1 = client_a.post(f"/contacts/{c.id}/variables", json={"key": "plan", "value": "free"})
    var_id = r1.json()["id"]

    r2 = client_a.patch(f"/contacts/{c.id}/variables/{var_id}", json={"value": "pro"})
    assert r2.status_code == 200
    assert r2.json()["value"] == "pro"


def test_delete_variable(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Var Test")
    db.commit()

    r1 = client_a.post(f"/contacts/{c.id}/variables", json={"key": "plan", "value": "free"})
    var_id = r1.json()["id"]

    r2 = client_a.delete(f"/contacts/{c.id}/variables/{var_id}")
    assert r2.status_code == 204

    r3 = client_a.get(f"/contacts/{c.id}/variables")
    assert r3.json() == []


def test_variable_cross_tenant_contact_returns_404(
    db: Session, user_a: User, workspace_a: Workspace, workspace_b: Workspace,
):
    c = _seed_contact(db, workspace_b, name="Other WS")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.post(f"/contacts/{c.id}/variables", json={"key": "k", "value": "v"})
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 9. CONVERSATIONS FILTER BY CONTACT_ID
# ══════════════════════════════════════════════════════════════════════════════


def _seed_conversation(db: Session, workspace: Workspace, contact: Contact, user: User) -> Conversation:
    agent = Agent(
        workspace_id=workspace.id,
        name=f"Agent-{uuid.uuid4().hex[:4]}",
        system_prompt="test",
        created_by_user_id=user.id,
    )
    db.add(agent)
    db.flush()
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        agent_id=agent.id,
        channel_type="web_widget",
        status="open",
    )
    db.add(conv)
    db.flush()
    return conv


def test_conversations_filter_by_contact_id(
    db: Session, client_a, workspace_a: Workspace, user_a: User,
):
    c1 = _seed_contact(db, workspace_a, name="Contact One")
    c2 = _seed_contact(db, workspace_a, name="Contact Two")
    conv1 = _seed_conversation(db, workspace_a, c1, user_a)
    _seed_conversation(db, workspace_a, c2, user_a)
    db.commit()

    r = client_a.get(f"/conversations?contact_id={c1.id}")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert ids == [str(conv1.id)]


def test_conversations_filter_contact_id_no_results(
    db: Session, client_a, workspace_a: Workspace, user_a: User,
):
    c = _seed_contact(db, workspace_a, name="No Conv")
    db.commit()

    r = client_a.get(f"/conversations?contact_id={c.id}")
    assert r.status_code == 200
    assert r.json() == []


def test_conversations_filter_contact_cross_tenant_returns_empty(
    db: Session,
    user_a: User, workspace_a: Workspace,
    user_b: User, workspace_b: Workspace,
):
    c_b = _seed_contact(db, workspace_b, name="WS-B contact")
    _seed_conversation(db, workspace_b, c_b, user_b)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.get(f"/conversations?contact_id={c_b.id}")
    assert r.status_code == 200
    assert r.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# 10. PHONE E.164 NORMALISATION (Clientes.1.1)
# ══════════════════════════════════════════════════════════════════════════════


def test_phone_e164_stored_as_is(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "+5537999999999"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+5537999999999"


def test_phone_national_11digits_normalised_to_br(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "37999999999"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+5537999999999"


def test_phone_national_10digits_normalised_to_br(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "3799999999"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+553799999999"


def test_phone_formatted_br_normalised(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "(37) 99999-9999"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+5537999999999"


def test_phone_with_spaces_normalised(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "37 99999-9999"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+5537999999999"


def test_phone_with_country_no_plus_normalised(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "5537999999999"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+5537999999999"


def test_phone_with_plus_spaces_normalised(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "+55 37 99999-9999"})
    assert r.status_code == 201
    assert r.json()["phone"] == "+5537999999999"


def test_phone_dedup_equivalent_formats_rejected(db: Session, client_a, workspace_a):
    r1 = client_a.post("/contacts", json={"phone": "+5537999999999"})
    assert r1.status_code == 201

    # Different format, same number
    r2 = client_a.post("/contacts", json={"phone": "(37) 99999-9999"})
    assert r2.status_code == 409


def test_phone_dedup_no_plus_vs_e164(db: Session, client_a, workspace_a):
    client_a.post("/contacts", json={"phone": "5537999999999"})

    r = client_a.post("/contacts", json={"phone": "+5537999999999"})
    assert r.status_code == 409


def test_phone_same_number_other_workspace_allowed(
    db: Session, client_a, workspace_b: Workspace,
):
    _seed_contact(db, workspace_b, phone="+5537999999999", name="WS-B")
    db.commit()

    r = client_a.post("/contacts", json={"phone": "+5537999999999"})
    assert r.status_code == 201


def test_phone_update_normalised(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"phone": "(37) 99999-9999"})
    assert r.status_code == 200
    assert r.json()["phone"] == "+5537999999999"


def test_phone_too_short_rejected(db: Session, client_a):
    r = client_a.post("/contacts", json={"phone": "123"})
    assert r.status_code == 422


def test_phone_only_special_chars_treated_as_none(db: Session, client_a):
    # Only dashes/spaces — after stripping digits it's empty, treated as None
    # But we also need name or email for the contact to be valid
    r = client_a.post("/contacts", json={"name": "Test", "phone": "---"})
    # No digits → stored as None (not invalid, just empty)
    assert r.status_code == 201
    assert r.json()["phone"] is None


def test_phone_search_by_formatted_finds_e164(db: Session, client_a, workspace_a: Workspace):
    # Store in E.164
    _seed_contact(db, workspace_a, phone="+5537999999999", name="Busca")
    db.commit()

    # Search with formatted version (digit-only fallback)
    r = client_a.get("/contacts?q=37999999999")
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    phones = [c["phone"] for c in r.json()["items"]]
    assert "+5537999999999" in phones
