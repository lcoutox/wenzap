"""
Tests for PATCH /agents/{id} field semantics (Phase 2.1).

Rules:
- Field absent from JSON payload → value preserved (not touched).
- Field present as null in JSON → value cleared (only for clearable fields).
- Non-clearable fields sent as null → ignored (treated as absent).
"""


import uuid

from app.models.plan import Plan
from tests.conftest import (
    _make_ai_model,
    _make_client,
    _make_subscription,
    _make_user,
    _make_workspace,
)


def _setup(db):
    user = _make_user(db, f"patch-{uuid.uuid4().hex[:6]}@test.com", "Patch User")
    ws = _make_workspace(db, user, f"patch-ws-{uuid.uuid4().hex[:6]}", "Patch WS")
    p = Plan(
        code=f"patch_plan_{uuid.uuid4().hex[:6]}",
        name="Patch Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=5,
        users_limit=10,
        pipelines_limit=5,
        integrations_limit=5,
        monthly_ai_credits=10000,
        monthly_conversations=5000,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    _make_subscription(db, ws, p)
    model = _make_ai_model(db)
    return user, ws, model


def _create(client, model_id, **kwargs):
    defaults = {
        "name": "Test Agent",
        "description": "Original description",
        "system_prompt": "Original prompt",
        "persona": "Original persona",
        "ai_model_id": str(model_id),
    }
    defaults.update(kwargs)
    r = client.post("/agents", json=defaults)
    assert r.status_code == 201
    return r.json()["id"]


# ── Clearable fields: explicit null clears the value ─────────────────────────

def test_patch_null_clears_description(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        agent_id = _create(client, model.id)
        response = client.patch(f"/agents/{agent_id}", json={"description": None})
    assert response.status_code == 200
    assert response.json()["description"] is None


def test_patch_null_clears_persona(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        agent_id = _create(client, model.id)
        response = client.patch(f"/agents/{agent_id}", json={"persona": None})
    assert response.status_code == 200
    assert response.json()["persona"] is None


def test_patch_null_clears_system_prompt(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        agent_id = _create(client, model.id)
        response = client.patch(f"/agents/{agent_id}", json={"system_prompt": None})
    assert response.status_code == 200
    assert response.json()["system_prompt"] is None


# ── Absent fields: omitted fields are preserved ───────────────────────────────

def test_patch_omitted_description_is_preserved(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        agent_id = _create(client, model.id)
        # Patch only the name — description should stay
        response = client.patch(f"/agents/{agent_id}", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["description"] == "Original description"
    assert response.json()["system_prompt"] == "Original prompt"
    assert response.json()["persona"] == "Original persona"
    assert response.json()["name"] == "New Name"


def test_patch_omitted_persona_is_preserved(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        agent_id = _create(client, model.id)
        response = client.patch(f"/agents/{agent_id}", json={"description": None})
    assert response.status_code == 200
    # persona was not sent — must be preserved
    assert response.json()["persona"] == "Original persona"


def test_patch_omitted_system_prompt_is_preserved(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        agent_id = _create(client, model.id)
        response = client.patch(f"/agents/{agent_id}", json={"name": "Updated"})
    assert response.status_code == 200
    assert response.json()["system_prompt"] == "Original prompt"


# ── Non-clearable fields: null is ignored ────────────────────────────────────

def test_patch_null_name_is_ignored(db):
    """Sending name: null should not clear the name — it should be ignored."""
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        agent_id = _create(client, model.id)
        response = client.patch(f"/agents/{agent_id}", json={"name": None})
    assert response.status_code == 200
    assert response.json()["name"] == "Test Agent"


# ── Status filter ─────────────────────────────────────────────────────────────

def test_list_agents_with_active_filter(db):
    """GET /agents?status=active returns only active agents."""
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r1 = client.post("/agents", json={
                "name": "Active One",
                "system_prompt": "Hello",
                "ai_model_id": str(model.id),
            })
        client.patch(f"/agents/{r1.json()['id']}/status", json={"status": "active"})

        client.post("/agents", json={"name": "Draft One", "ai_model_id": str(model.id)})

        response = client.get("/agents?status=active")
    assert response.status_code == 200
    agents = response.json()
    assert all(a["status"] == "active" for a in agents)
    names = [a["name"] for a in agents]
    assert "Active One" in names
    assert "Draft One" not in names


# ── Tenant isolation for status endpoint ─────────────────────────────────────

def test_patch_status_of_agent_from_other_workspace_returns_404(
    db, client_a, subscription_a, workspace_b, user_b
):
    """PATCH /agents/{id}/status must return 404 for agents from other workspaces."""
    from app.enums import AgentStatus
    from app.models.agent import Agent

    model_b = _make_ai_model(db)
    agent_b = Agent(
        workspace_id=workspace_b.id,
        name="Agent B",
        system_prompt="Hello",
        ai_model_id=model_b.id,
        model_name=model_b.model_name,
        temperature=0.7,
        status=AgentStatus.draft.value,
        created_by_user_id=user_b.id,
    )
    db.add(agent_b)
    db.commit()
    db.refresh(agent_b)

    response = client_a.patch(f"/agents/{agent_b.id}/status", json={"status": "active"})
    assert response.status_code == 404
