"""
Tests for the /agents endpoints.

Covers: CRUD, tenant isolation, RBAC, validation.
Plan limits and status machine are tested in dedicated files.
"""

import uuid

from app.enums import MemberRole, MemberStatus
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_ai_model, _make_client, _make_user


def _agent_payload(ai_model_id: uuid.UUID, **kwargs) -> dict:
    defaults = {
        "name": "Support Agent",
        "description": "Handles support tickets",
        "system_prompt": "You are a helpful support agent.",
        "ai_model_id": str(ai_model_id),
        "temperature": 0.7,
    }
    defaults.update(kwargs)
    return defaults


# ── CREATE ────────────────────────────────────────────────────────────────────

def test_create_agent_returns_201(client_a, subscription_a, ai_model):
    response = client_a.post("/agents", json=_agent_payload(ai_model.id))
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Support Agent"
    assert body["status"] == "draft"
    assert body["ai_model_id"] == str(ai_model.id)
    assert body["model_name"] == ai_model.model_name


def test_create_agent_uses_workspace_from_context_not_body(
    client_a, subscription_a, workspace_b, ai_model
):
    """workspace_id in payload must be ignored — workspace comes from auth context."""
    payload = {**_agent_payload(ai_model.id), "workspace_id": str(workspace_b.id)}
    response = client_a.post("/agents", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["workspace_id"] != str(workspace_b.id)


def test_create_agent_snapshots_model_name(client_a, subscription_a, ai_model):
    response = client_a.post("/agents", json=_agent_payload(ai_model.id))
    assert response.status_code == 201
    body = response.json()
    assert body["model_name"] == ai_model.model_name
    assert body["ai_model_id"] == str(ai_model.id)
    assert body["temperature"] == 0.7
    assert body["status"] == "draft"


def test_create_agent_missing_ai_model_id_returns_422(client_a, subscription_a):
    response = client_a.post("/agents", json={"name": "Agent"})
    assert response.status_code == 422


def test_create_agent_invalid_ai_model_id_returns_404(client_a, subscription_a):
    response = client_a.post(
        "/agents", json={"name": "Agent", "ai_model_id": str(uuid.uuid4())}
    )
    assert response.status_code == 404


def test_create_agent_blocked_by_plan_returns_402(db, subscription_a):
    from app.models.plan import Plan
    from tests.conftest import _make_subscription, _make_workspace

    user = _make_user(db, f"blocked-{uuid.uuid4().hex[:6]}@t.com", "Blocked")
    ws = _make_workspace(db, user, f"blocked-ws-{uuid.uuid4().hex[:6]}", "Blocked WS")
    plan = Plan(
        code=f"starter_{uuid.uuid4().hex[:6]}",
        name="Starter",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=5,
        knowledge_bases_limit=5,
        users_limit=10,
        pipelines_limit=5,
        integrations_limit=5,
        monthly_ai_credits=1000,
        monthly_conversations=500,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    _make_subscription(db, ws, plan)

    # Model requires "growth" plan — workspace has "starter_xxx" which maps to tier=1
    growth_model = _make_ai_model(db, min_plan_code="growth")

    with _make_client(db, user, ws) as client:
        response = client.post(
            "/agents", json={"name": "Agent", "ai_model_id": str(growth_model.id)}
        )
    assert response.status_code == 402


# ── LIST ─────────────────────────────────────────────────────────────────────

def test_list_agents_excludes_archived_by_default(db, user_a, workspace_a):
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

    model = _make_ai_model(db)

    with _make_client(db, user_a, workspace_a) as client:
        client.post(
            "/agents",
            json=_agent_payload(model.id, name="Active Agent", system_prompt="Hello"),
        )
        r = client.post("/agents", json=_agent_payload(model.id, name="To Archive"))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

        response = client.get("/agents")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "Active Agent" in names
    assert "To Archive" not in names


def test_list_agents_with_status_archived_filter(client_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id, name="Will Archive"))
    agent_id = r.json()["id"]
    client_a.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

    response = client_a.get("/agents?status=archived")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "Will Archive" in names


def test_list_agents_with_draft_filter(client_a, subscription_a, ai_model):
    client_a.post("/agents", json=_agent_payload(ai_model.id, name="Draft One"))
    response = client_a.get("/agents?status=draft")
    assert response.status_code == 200
    for agent in response.json():
        assert agent["status"] == "draft"


def test_list_agents_invalid_status_returns_422(client_a):
    response = client_a.get("/agents?status=invalid_status")
    assert response.status_code == 422


# ── GET BY ID ─────────────────────────────────────────────────────────────────

def test_get_agent_by_id(client_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    response = client_a.get(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["id"] == agent_id


def test_get_nonexistent_agent_returns_404(client_a):
    response = client_a.get(f"/agents/{uuid.uuid4()}")
    assert response.status_code == 404


# ── UPDATE ────────────────────────────────────────────────────────────────────

def test_update_agent_name(client_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    response = client_a.patch(f"/agents/{agent_id}", json={"name": "Updated Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


def test_update_agent_model(db, client_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]

    new_model = _make_ai_model(db)
    response = client_a.patch(
        f"/agents/{agent_id}", json={"ai_model_id": str(new_model.id)}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ai_model_id"] == str(new_model.id)
    assert body["model_name"] == new_model.model_name


def test_update_archived_agent_returns_400(client_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    client_a.patch(f"/agents/{agent_id}/status", json={"status": "archived"})
    response = client_a.patch(f"/agents/{agent_id}", json={"name": "New Name"})
    assert response.status_code == 400


# ── DELETE (archive) ──────────────────────────────────────────────────────────

def test_delete_archives_agent(client_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    response = client_a.delete(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    assert response.json()["id"] == agent_id


def test_delete_does_not_physically_remove(client_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    client_a.delete(f"/agents/{agent_id}")
    response = client_a.get(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


# ── TENANT ISOLATION ─────────────────────────────────────────────────────────

def _create_agent_directly(db, workspace_id, user_id, model, name="Agent B"):
    from app.enums import AgentStatus
    from app.models.agent import Agent
    agent = Agent(
        workspace_id=workspace_id,
        name=name,
        system_prompt="Hello",
        ai_model_id=model.id,
        model_name=model.model_name,
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
    model = _make_ai_model(db)
    agent_b = _create_agent_directly(db, workspace_b.id, user_b.id, model)
    response = client_a.get(f"/agents/{agent_b.id}")
    assert response.status_code == 404


def test_patch_agent_from_other_workspace_returns_404(
    db, client_a, subscription_a, workspace_b, user_b
):
    model = _make_ai_model(db)
    agent_b = _create_agent_directly(db, workspace_b.id, user_b.id, model)
    response = client_a.patch(f"/agents/{agent_b.id}", json={"name": "Hacked"})
    assert response.status_code == 404


def test_delete_agent_from_other_workspace_returns_404(
    db, client_a, subscription_a, workspace_b, user_b
):
    model = _make_ai_model(db)
    agent_b = _create_agent_directly(db, workspace_b.id, user_b.id, model)
    response = client_a.delete(f"/agents/{agent_b.id}")
    assert response.status_code == 404


def test_list_agents_does_not_include_other_workspace(
    db, client_a, subscription_a, workspace_b, user_b
):
    model = _make_ai_model(db)
    _create_agent_directly(db, workspace_b.id, user_b.id, model, name="Workspace B Agent")
    response = client_a.get("/agents")
    assert response.status_code == 200
    names = [a["name"] for a in response.json()]
    assert "Workspace B Agent" not in names


# ── RBAC ─────────────────────────────────────────────────────────────────────

def test_viewer_cannot_create_agent(db, user_a, workspace_a, subscription_a, ai_model):
    viewer = _make_viewer(db, workspace_a)
    with _make_client(db, viewer, workspace_a) as client:
        response = client.post("/agents", json=_agent_payload(ai_model.id))
    assert response.status_code == 403


def test_viewer_cannot_edit_agent(db, client_a, user_a, workspace_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    viewer = _make_viewer(db, workspace_a)
    with _make_client(db, viewer, workspace_a) as client:
        response = client.patch(f"/agents/{agent_id}", json={"name": "Hacked"})
    assert response.status_code == 403


def test_viewer_cannot_change_status(db, client_a, user_a, workspace_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    viewer = _make_viewer(db, workspace_a)
    with _make_client(db, viewer, workspace_a) as client:
        response = client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
    assert response.status_code == 403


def test_member_cannot_archive_agent(db, client_a, workspace_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    member = _make_member(db, workspace_a)
    with _make_client(db, member, workspace_a) as client:
        response = client.delete(f"/agents/{agent_id}")
    assert response.status_code == 403


def test_admin_can_archive_agent(db, client_a, workspace_a, subscription_a, ai_model):
    r = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = r.json()["id"]
    admin = _make_admin(db, workspace_a)
    with _make_client(db, admin, workspace_a) as client:
        response = client.delete(f"/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_inactive_member_cannot_create_agent(db, user_a, workspace_a, subscription_a, ai_model):
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
        response = client.post("/agents", json=_agent_payload(ai_model.id))
    assert response.status_code == 403


# ── VALIDATION ────────────────────────────────────────────────────────────────

def test_empty_name_returns_422(client_a):
    response = client_a.post("/agents", json={"name": "", "ai_model_id": str(uuid.uuid4())})
    assert response.status_code == 422


def test_temperature_out_of_range_returns_422(client_a, ai_model):
    response = client_a.post(
        "/agents", json={"name": "Agent", "ai_model_id": str(ai_model.id), "temperature": 1.5}
    )
    assert response.status_code == 422


def test_temperature_negative_returns_422(client_a, ai_model):
    response = client_a.post(
        "/agents", json={"name": "Agent", "ai_model_id": str(ai_model.id), "temperature": -0.1}
    )
    assert response.status_code == 422


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_viewer(db, workspace):
    u = _make_user(db, f"viewer-{uuid.uuid4().hex[:6]}@test.com", "Viewer")
    m = WorkspaceMember(
        workspace_id=workspace.id, user_id=u.id,
        role=MemberRole.viewer, status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return u


def _make_member(db, workspace):
    u = _make_user(db, f"member-{uuid.uuid4().hex[:6]}@test.com", "Member")
    m = WorkspaceMember(
        workspace_id=workspace.id, user_id=u.id,
        role=MemberRole.member, status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return u


def _make_admin(db, workspace):
    u = _make_user(db, f"admin-{uuid.uuid4().hex[:6]}@test.com", "Admin")
    m = WorkspaceMember(
        workspace_id=workspace.id, user_id=u.id,
        role=MemberRole.admin, status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return u


# ── Guided / Advanced Instructions ────────────────────────────────────────────

def test_create_agent_defaults_instructions_mode_to_guided(client_a, subscription_a, ai_model):
    response = client_a.post("/agents", json=_agent_payload(ai_model.id))
    assert response.status_code == 201
    data = response.json()
    assert data["instructions_mode"] == "guided"
    assert data["guided_config"] is None
    assert data["advanced_prompt"] is None


def test_patch_agent_to_advanced_mode(client_a, subscription_a, ai_model):
    create = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = create.json()["id"]
    response = client_a.patch(f"/agents/{agent_id}", json={
        "instructions_mode": "advanced",
        "advanced_prompt": "You are a specialist sales agent.",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["instructions_mode"] == "advanced"
    assert data["advanced_prompt"] == "You are a specialist sales agent."


def test_patch_agent_guided_config(client_a, subscription_a, ai_model):
    create = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = create.json()["id"]
    response = client_a.patch(f"/agents/{agent_id}", json={
        "instructions_mode": "guided",
        "guided_config": {
            "role": "customer_support",
            "posture": "welcoming",
            "do_items": ["answer_company_questions"],
            "dont_items": ["no_fake_prices"],
            "custom_should_do": ["Always greet the user by name"],
            "custom_should_not_do": ["Never discuss competitors"],
        },
    })
    assert response.status_code == 200
    data = response.json()
    assert data["instructions_mode"] == "guided"
    cfg = data["guided_config"]
    assert cfg["role"] == "customer_support"
    assert "answer_company_questions" in cfg["do_items"]
    assert cfg["custom_should_do"] == ["Always greet the user by name"]
    assert cfg["custom_should_not_do"] == ["Never discuss competitors"]


def test_patch_guided_config_invalid_enum_returns_422(client_a, subscription_a, ai_model):
    create = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = create.json()["id"]
    response = client_a.patch(f"/agents/{agent_id}", json={
        "guided_config": {"role": "nonexistent_role"},
    })
    assert response.status_code == 422


def test_patch_invalid_instructions_mode_returns_422(client_a, subscription_a, ai_model):
    create = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = create.json()["id"]
    response = client_a.patch(f"/agents/{agent_id}", json={
        "instructions_mode": "invalid_mode",
    })
    assert response.status_code == 422


def test_guided_config_custom_items_too_long_returns_422(client_a, subscription_a, ai_model):
    create = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = create.json()["id"]
    response = client_a.patch(f"/agents/{agent_id}", json={
        "guided_config": {"custom_should_do": ["x" * 501]},
    })
    assert response.status_code == 422


def test_patch_mode_switch_preserves_other_fields(client_a, subscription_a, ai_model):
    """Switching mode should not wipe response_style or language_mode."""
    create = client_a.post("/agents", json=_agent_payload(ai_model.id))
    agent_id = create.json()["id"]
    # Set style first
    client_a.patch(f"/agents/{agent_id}", json={"response_style": "concise", "language_mode": "pt"})
    # Switch mode
    switch = client_a.patch(f"/agents/{agent_id}", json={"instructions_mode": "advanced"})
    data = switch.json()
    assert data["response_style"] == "concise"
    assert data["language_mode"] == "pt"
