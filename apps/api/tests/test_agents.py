"""
Tests for the /agents endpoints.

Covers: CRUD, tenant isolation, RBAC, validation.
Plan limits and status machine are tested in dedicated files.
"""

import uuid

from app.enums import MemberRole, MemberStatus
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client

VALID_AGENT = {
    "name": "Support Agent",
    "description": "Handles support tickets",
    "system_prompt": "You are a helpful support agent.",
    "model_provider": "anthropic",
    "model_name": "claude-sonnet-4-6",
    "temperature": 0.7,
}


# ── CREATE ────────────────────────────────────────────────────────────────────

def test_create_agent_returns_201(client_a, subscription_a):
    response = client_a.post("/agents", json=VALID_AGENT)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Support Agent"
    assert body["status"] == "draft"


def test_create_agent_uses_workspace_from_context_not_body(
    client_a, subscription_a, workspace_b
):
    """workspace_id in payload must be ignored — workspace comes from auth context."""
    payload = {**VALID_AGENT, "workspace_id": str(workspace_b.id)}
    response = client_a.post("/agents", json=payload)
    assert response.status_code == 201
    body = response.json()
    # workspace_b.id must NOT be used
    assert body["workspace_id"] != str(workspace_b.id)


def test_create_agent_defaults(client_a, subscription_a):
    response = client_a.post("/agents", json={"name": "Minimal Agent"})
    assert response.status_code == 201
    body = response.json()
    assert body["model_provider"] == "anthropic"
    assert body["model_name"] == "claude-sonnet-4-6"
    assert body["temperature"] == 0.7
    assert body["status"] == "draft"


# ── LIST ─────────────────────────────────────────────────────────────────────

def test_list_agents_excludes_archived_by_default(db, user_a, workspace_a):
    """Uses a plan with limit >= 2 to create two agents."""
    from app.models.plan import Plan
    from tests.conftest import _make_subscription

    plan = Plan(
        code=f"list_test_{uuid.uuid4().hex[:6]}",
        name="List Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=5,
        knowledge_bases_limit=5,
        users_limit=10,
        pipelines_limit=5,
        integrations_limit=5,
        monthly_ai_credits=10000,
        monthly_conversations=5000,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    _make_subscription(db, workspace_a, plan)

    with _make_client(db, user_a, workspace_a) as client:
        client.post("/agents", json={"name": "Active Agent", "system_prompt": "Hello"})
        r = client.post("/agents", json={"name": "To Archive"})
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

        response = client.get("/agents")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "Active Agent" in names
    assert "To Archive" not in names


def test_list_agents_with_status_archived_filter(client_a, subscription_a):
    r = client_a.post("/agents", json={"name": "Will Archive"})
    agent_id = r.json()["id"]
    client_a.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

    response = client_a.get("/agents?status=archived")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "Will Archive" in names


def test_list_agents_with_draft_filter(client_a, subscription_a):
    client_a.post("/agents", json={"name": "Draft One"})
    response = client_a.get("/agents?status=draft")
    assert response.status_code == 200
    for agent in response.json():
        assert agent["status"] == "draft"


def test_list_agents_invalid_status_returns_422(client_a):
    response = client_a.get("/agents?status=invalid_status")
    assert response.status_code == 422


# ── GET BY ID ─────────────────────────────────────────────────────────────────

def test_get_agent_by_id(client_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    response = client_a.get(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["id"] == agent_id


def test_get_nonexistent_agent_returns_404(client_a):
    response = client_a.get(f"/agents/{uuid.uuid4()}")
    assert response.status_code == 404


# ── UPDATE ────────────────────────────────────────────────────────────────────

def test_update_agent_name(client_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    response = client_a.patch(f"/agents/{agent_id}", json={"name": "Updated Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


def test_update_archived_agent_returns_400(client_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    client_a.patch(f"/agents/{agent_id}/status", json={"status": "archived"})
    response = client_a.patch(f"/agents/{agent_id}", json={"name": "New Name"})
    assert response.status_code == 400


# ── DELETE (archive) ──────────────────────────────────────────────────────────

def test_delete_archives_agent(client_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    response = client_a.delete(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    assert response.json()["id"] == agent_id


def test_delete_does_not_physically_remove(client_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    client_a.delete(f"/agents/{agent_id}")
    # Should still be retrievable via direct GET
    response = client_a.get(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


# ── TENANT ISOLATION ─────────────────────────────────────────────────────────

def _create_agent_directly(db, workspace_id, user_id, name="Agent B"):
    """Create an agent directly via service to avoid nested _make_client / override collision."""
    from app.enums import AgentStatus
    from app.models.agent import Agent
    agent = Agent(
        workspace_id=workspace_id,
        name=name,
        system_prompt="Hello",
        model_provider="anthropic",
        model_name="claude-sonnet-4-6",
        temperature=0.7,
        status=AgentStatus.draft.value,
        created_by_user_id=user_id,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def test_get_agent_from_other_workspace_returns_404(
    db, client_a, subscription_a, workspace_b, user_b
):
    agent_b = _create_agent_directly(db, workspace_b.id, user_b.id)
    response = client_a.get(f"/agents/{agent_b.id}")
    assert response.status_code == 404


def test_patch_agent_from_other_workspace_returns_404(
    db, client_a, subscription_a, workspace_b, user_b
):
    agent_b = _create_agent_directly(db, workspace_b.id, user_b.id)
    response = client_a.patch(f"/agents/{agent_b.id}", json={"name": "Hacked"})
    assert response.status_code == 404


def test_delete_agent_from_other_workspace_returns_404(
    db, client_a, subscription_a, workspace_b, user_b
):
    agent_b = _create_agent_directly(db, workspace_b.id, user_b.id)
    response = client_a.delete(f"/agents/{agent_b.id}")
    assert response.status_code == 404


def test_list_agents_does_not_include_other_workspace(
    db, client_a, subscription_a, workspace_b, user_b
):
    _create_agent_directly(db, workspace_b.id, user_b.id, name="Workspace B Agent")
    response = client_a.get("/agents")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "Workspace B Agent" not in names


# ── RBAC ─────────────────────────────────────────────────────────────────────

def test_viewer_cannot_create_agent(db, user_a, workspace_a, subscription_a):
    viewer = _make_viewer(db, workspace_a)
    with _make_client(db, viewer, workspace_a) as client:
        response = client.post("/agents", json=VALID_AGENT)
    assert response.status_code == 403


def test_viewer_cannot_edit_agent(db, client_a, user_a, workspace_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    viewer = _make_viewer(db, workspace_a)
    with _make_client(db, viewer, workspace_a) as client:
        response = client.patch(f"/agents/{agent_id}", json={"name": "Hacked"})
    assert response.status_code == 403


def test_viewer_cannot_change_status(db, client_a, user_a, workspace_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    viewer = _make_viewer(db, workspace_a)
    with _make_client(db, viewer, workspace_a) as client:
        response = client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
    assert response.status_code == 403


def test_member_cannot_archive_agent(db, client_a, workspace_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    member = _make_member(db, workspace_a)
    with _make_client(db, member, workspace_a) as client:
        response = client.delete(f"/agents/{agent_id}")
    assert response.status_code == 403


def test_admin_can_archive_agent(db, client_a, workspace_a, subscription_a):
    r = client_a.post("/agents", json=VALID_AGENT)
    agent_id = r.json()["id"]
    admin = _make_admin(db, workspace_a)
    with _make_client(db, admin, workspace_a) as client:
        response = client.delete(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_inactive_member_cannot_create_agent(db, user_a, workspace_a, subscription_a):
    from tests.conftest import _make_user
    inactive_user = _make_user(db, "inactive@test.com", "Inactive")
    m = WorkspaceMember(
        workspace_id=workspace_a.id,
        user_id=inactive_user.id,
        role=MemberRole.member,
        status=MemberStatus.inactive,
    )
    db.add(m)
    db.commit()
    with _make_client(db, inactive_user, workspace_a) as client:
        response = client.post("/agents", json=VALID_AGENT)
    assert response.status_code == 403


# ── VALIDATION ────────────────────────────────────────────────────────────────

def test_empty_name_returns_422(client_a):
    response = client_a.post("/agents", json={"name": ""})
    assert response.status_code == 422


def test_temperature_out_of_range_returns_422(client_a):
    response = client_a.post("/agents", json={"name": "Agent", "temperature": 1.5})
    assert response.status_code == 422


def test_temperature_negative_returns_422(client_a):
    response = client_a.post("/agents", json={"name": "Agent", "temperature": -0.1})
    assert response.status_code == 422


def test_invalid_model_provider_returns_422(client_a):
    response = client_a.post(
        "/agents", json={"name": "Agent", "model_provider": "INVALID PROVIDER!"}
    )
    assert response.status_code == 422


def test_invalid_model_name_returns_422(client_a):
    response = client_a.post("/agents", json={"name": "Agent", "model_name": "invalid model name!"})
    assert response.status_code == 422


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_viewer(db, workspace):
    from tests.conftest import _make_user
    u = _make_user(db, f"viewer-{uuid.uuid4().hex[:6]}@test.com", "Viewer")
    m = WorkspaceMember(
        workspace_id=workspace.id, user_id=u.id,
        role=MemberRole.viewer, status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return u


def _make_member(db, workspace):
    from tests.conftest import _make_user
    u = _make_user(db, f"member-{uuid.uuid4().hex[:6]}@test.com", "Member")
    m = WorkspaceMember(
        workspace_id=workspace.id, user_id=u.id,
        role=MemberRole.member, status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return u


def _make_admin(db, workspace):
    from tests.conftest import _make_user
    u = _make_user(db, f"admin-{uuid.uuid4().hex[:6]}@test.com", "Admin")
    m = WorkspaceMember(
        workspace_id=workspace.id, user_id=u.id,
        role=MemberRole.admin, status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return u
