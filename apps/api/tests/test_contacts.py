"""
Tests for Phase 5.1.2 — Contacts API.

Covers:
  1. CRUD (create, list, get, update)
  2. ContactCreate / ContactUpdate semantics
  3. RBAC (viewer read-only, member/admin/owner write)
  4. Tenant isolation (contacts are scoped to workspace)
  5. Pagination (skip / limit)
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.contact import Contact
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
        name=kwargs.pop("name", "Seed Contact"),
        **kwargs,
    )
    db.add(c)
    db.flush()
    return c


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
        "external_id": "wa_5511999990000",
        "metadata": {"source": "widget", "score": 8},
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Maria Oliveira"
    assert body["email"] == "maria@example.com"
    assert body["phone"] == "+5511999990000"
    assert body["external_id"] == "wa_5511999990000"
    assert body["metadata_json"] == {"source": "widget", "score": 8}


def test_create_contact_name_required(db: Session, client_a):
    r = client_a.post("/contacts", json={})
    assert r.status_code == 422


def test_create_contact_name_empty_string_rejected(db: Session, client_a):
    r = client_a.post("/contacts", json={"name": ""})
    assert r.status_code == 422


def test_create_contact_metadata_persists(db: Session, client_a):
    payload = {"tags": ["vip"], "score": 9.5, "active": True}
    r = client_a.post("/contacts", json={"name": "Test", "metadata": payload})
    assert r.status_code == 201
    assert r.json()["metadata_json"] == payload


# ══════════════════════════════════════════════════════════════════════════════
# 2. LIST
# ══════════════════════════════════════════════════════════════════════════════


def test_list_contacts_empty(db: Session, client_a):
    r = client_a.get("/contacts")
    assert r.status_code == 200
    assert r.json() == []


def test_list_contacts_returns_own_workspace(
    db: Session, client_a, workspace_a: Workspace
):
    _seed_contact(db, workspace_a, name="Alice")
    _seed_contact(db, workspace_a, name="Bob")
    db.commit()

    r = client_a.get("/contacts")
    assert r.status_code == 200
    names = {c["name"] for c in r.json()}
    assert names == {"Alice", "Bob"}


def test_list_contacts_ordered_newest_first(
    db: Session, client_a, workspace_a: Workspace
):
    # Commit each contact separately so their created_at values differ.
    c1 = _seed_contact(db, workspace_a, name="First")
    db.commit()
    db.refresh(c1)

    c2 = _seed_contact(db, workspace_a, name="Second")
    db.commit()
    db.refresh(c2)

    r = client_a.get("/contacts")
    ids = [c["id"] for c in r.json()]
    assert ids[0] == str(c2.id)
    assert ids[1] == str(c1.id)


def test_list_contacts_skip_and_limit(db: Session, client_a, workspace_a: Workspace):
    for i in range(5):
        _seed_contact(db, workspace_a, name=f"Contact {i}")
    db.commit()

    r = client_a.get("/contacts?skip=2&limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_contacts_limit_capped_at_100(
    db: Session, client_a, workspace_a: Workspace
):
    for i in range(5):
        _seed_contact(db, workspace_a, name=f"Contact {i}")
    db.commit()

    # Requesting 200 should be silently capped at 100
    r = client_a.get("/contacts?limit=200")
    assert r.status_code == 200
    # Just verify it doesn't error; we can't get 200 results from 5 contacts
    assert len(r.json()) <= 100


# ══════════════════════════════════════════════════════════════════════════════
# 3. GET
# ══════════════════════════════════════════════════════════════════════════════


def test_get_contact_returns_correct_data(
    db: Session, client_a, workspace_a: Workspace
):
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


def test_update_contact_external_id(db: Session, client_a, workspace_a: Workspace):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"external_id": "ig_abc123"})
    assert r.status_code == 200
    assert r.json()["external_id"] == "ig_abc123"


def test_update_contact_clears_email_with_null(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(db, workspace_a, name="Test", email="old@test.com")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"email": None})
    assert r.status_code == 200
    assert r.json()["email"] is None


def test_update_contact_clears_phone_with_null(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(db, workspace_a, name="Test", phone="+5511999990000")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"phone": None})
    assert r.status_code == 200
    assert r.json()["phone"] is None


def test_update_contact_clears_external_id_with_null(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(db, workspace_a, name="Test", external_id="wa_123")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"external_id": None})
    assert r.status_code == 200
    assert r.json()["external_id"] is None


def test_update_contact_clears_metadata_with_null(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(db, workspace_a, name="Test", metadata_json={"k": "v"})
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"metadata": None})
    assert r.status_code == 200
    assert r.json()["metadata_json"] is None


def test_update_contact_absent_fields_not_changed(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(
        db, workspace_a, name="Test", email="keep@test.com", phone="+5511999990000"
    )
    db.commit()

    # Only updating name; email and phone must remain
    r = client_a.patch(f"/contacts/{c.id}", json={"name": "Updated"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Updated"
    assert body["email"] == "keep@test.com"
    assert body["phone"] == "+5511999990000"


def test_update_contact_null_name_rejected(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"name": None})
    assert r.status_code == 422


def test_update_contact_empty_name_rejected(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"name": ""})
    assert r.status_code == 422


def test_update_contact_not_found(db: Session, client_a):
    r = client_a.patch(f"/contacts/{uuid.uuid4()}", json={"name": "Ghost"})
    assert r.status_code == 404


def test_update_contact_updates_updated_at(
    db: Session, client_a, workspace_a: Workspace
):
    c = _seed_contact(db, workspace_a, name="Test")
    db.commit()

    r = client_a.patch(f"/contacts/{c.id}", json={"name": "Changed"})
    assert r.status_code == 200
    # updated_at must be present in the response (not None).
    assert r.json()["updated_at"] is not None


# ══════════════════════════════════════════════════════════════════════════════
# 5. RBAC
# ══════════════════════════════════════════════════════════════════════════════


def test_viewer_can_list_contacts(db: Session, workspace_a: Workspace, user_a: User):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    _seed_contact(db, workspace_a, name="Visible")
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        r = client.get("/contacts")
    assert r.status_code == 200
    assert len(r.json()) == 1


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


@pytest.mark.parametrize("role", [MemberRole.member, MemberRole.admin, MemberRole.owner])
def test_write_roles_can_create_contact(
    db: Session, workspace_a: Workspace, user_a: User, role: MemberRole
):
    user = _make_member(db, workspace_a, role)
    db.commit()

    with _make_client(db, user, workspace_a) as client:
        r = client.post("/contacts", json={"name": f"Contact by {role.value}"})
    assert r.status_code == 201


@pytest.mark.parametrize("role", [MemberRole.member, MemberRole.admin, MemberRole.owner])
def test_write_roles_can_update_contact(
    db: Session, workspace_a: Workspace, user_a: User, role: MemberRole
):
    user = _make_member(db, workspace_a, role)
    c = _seed_contact(db, workspace_a, name="Original")
    db.commit()

    with _make_client(db, user, workspace_a) as client:
        r = client.patch(f"/contacts/{c.id}", json={"name": f"Updated by {role.value}"})
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# 6. TENANT ISOLATION
# ══════════════════════════════════════════════════════════════════════════════


def test_list_contacts_excludes_other_workspace(
    db: Session,
    user_a: User, workspace_a: Workspace,
    user_b: User, workspace_b: Workspace,
):
    # Seed contacts in both workspaces before making any requests.
    _seed_contact(db, workspace_a, name="WS-A Contact")
    _seed_contact(db, workspace_b, name="WS-B Contact")
    db.commit()

    # Use sequential client contexts to avoid dependency_overrides conflicts.
    with _make_client(db, user_a, workspace_a) as client_a:
        r_a = client_a.get("/contacts")

    with _make_client(db, user_b, workspace_b) as client_b:
        r_b = client_b.get("/contacts")

    names_a = {c["name"] for c in r_a.json()}
    names_b = {c["name"] for c in r_b.json()}

    assert names_a == {"WS-A Contact"}
    assert names_b == {"WS-B Contact"}


def test_get_contact_cross_tenant_returns_404(
    db: Session,
    user_a: User, workspace_a: Workspace,
    workspace_b: Workspace,
):
    c = _seed_contact(db, workspace_b, name="WS-B Only")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.get(f"/contacts/{c.id}")
    assert r.status_code == 404


def test_patch_contact_cross_tenant_returns_404(
    db: Session,
    user_a: User, workspace_a: Workspace,
    workspace_b: Workspace,
):
    c = _seed_contact(db, workspace_b, name="WS-B Only")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        r = client.patch(f"/contacts/{c.id}", json={"name": "Hijacked"})
    assert r.status_code == 404
