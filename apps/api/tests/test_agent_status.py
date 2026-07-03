"""
Tests for the agent status state machine.

Valid transitions:
    draft    -> active (requires system_prompt)
    draft    -> archived
    active   -> inactive
    active   -> archived
    inactive -> active
    inactive -> archived
    archived -> * (blocked — terminal state)
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
    """Returns (user, workspace, ai_model)."""
    user = _make_user(db, f"status-{uuid.uuid4().hex[:6]}@test.com", "Status User")
    ws = _make_workspace(db, user, f"status-ws-{uuid.uuid4().hex[:6]}", "Status WS")
    p = Plan(
        code=f"status_plan_{uuid.uuid4().hex[:6]}",
        name="Status Plan",
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


def _with_prompt(model_id):
    return {
        "name": "Agent",
        "system_prompt": "You are a helpful assistant.",
        "ai_model_id": str(model_id),
    }


def _without_prompt(model_id):
    return {"name": "Agent Without Prompt", "ai_model_id": str(model_id)}


# ── draft → active ────────────────────────────────────────────────────────────

def test_draft_to_active_with_system_prompt(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_with_prompt(model.id))
        agent_id = r.json()["id"]
        assert r.json()["status"] == "draft"

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        assert response.status_code == 200
        assert response.json()["status"] == "active"


def test_draft_to_active_without_system_prompt_returns_400(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_without_prompt(model.id))
        agent_id = r.json()["id"]

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        assert response.status_code == 400


def test_draft_to_active_with_empty_system_prompt_returns_400(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json={
            "name": "Agent", "system_prompt": "   ", "ai_model_id": str(model.id)
        })
        agent_id = r.json()["id"]

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        assert response.status_code == 400


# ── draft → archived ──────────────────────────────────────────────────────────

def test_draft_to_archived(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_without_prompt(model.id))
        agent_id = r.json()["id"]

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})
        assert response.status_code == 200
        assert response.json()["status"] == "archived"


# ── active → inactive ─────────────────────────────────────────────────────────

def test_active_to_inactive(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_with_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "active"})

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "inactive"})
        assert response.status_code == 200
        assert response.json()["status"] == "inactive"


# ── active → archived ─────────────────────────────────────────────────────────

def test_active_to_archived(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_with_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "active"})

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})
        assert response.status_code == 200
        assert response.json()["status"] == "archived"


# ── inactive → active ─────────────────────────────────────────────────────────

def test_inactive_to_active(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_with_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        client.patch(f"/agents/{agent_id}/status", json={"status": "inactive"})

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        assert response.status_code == 200
        assert response.json()["status"] == "active"


# ── inactive → archived ───────────────────────────────────────────────────────

def test_inactive_to_archived(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_with_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        client.patch(f"/agents/{agent_id}/status", json={"status": "inactive"})

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})
        assert response.status_code == 200
        assert response.json()["status"] == "archived"


# ── archived → * (terminal) ───────────────────────────────────────────────────

def test_archived_to_active_returns_400(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_with_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        assert response.status_code == 400


def test_archived_to_inactive_returns_400(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_with_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "inactive"})
        assert response.status_code == 400


def test_archived_to_draft_returns_400(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_without_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

        response = client.patch(f"/agents/{agent_id}/status", json={"status": "draft"})
        assert response.status_code == 400


# ── PATCH on archived agent ───────────────────────────────────────────────────

def test_patch_archived_agent_returns_400(db):
    user, ws, model = _setup(db)
    with _make_client(db, user, ws) as client:
        r = client.post("/agents", json=_without_prompt(model.id))
        agent_id = r.json()["id"]
        client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

        response = client.patch(f"/agents/{agent_id}", json={"name": "New Name"})
        assert response.status_code == 400
