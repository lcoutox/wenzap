"""
Tests for agent satellite settings (agent_prompt_settings, agent_model_settings).

Covers:
- create_agent creates both satellite records
- update_agent routes fields to correct satellite tables
- AgentOut fields are sourced from satellites (not agents.*)
- update_agent_status validates system_prompt from agent_prompt_settings
- on-demand creation of settings for agents that predate migration (fallback)
- tenant isolation of settings
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from tests.conftest import (
    _make_ai_model,
    _make_client,
    _make_subscription,
    _make_user,
    _make_workspace,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_prompt_settings(db: Session, agent_id: uuid.UUID) -> AgentPromptSettings | None:
    return db.scalar(
        select(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent_id)
    )


def _get_model_settings(db: Session, agent_id: uuid.UUID) -> AgentModelSettings | None:
    return db.scalar(
        select(AgentModelSettings).where(AgentModelSettings.agent_id == agent_id)
    )


def _create_agent_via_api(
    client: TestClient,
    ai_model_id: str,
    *,
    name: str = "Test Agent",
    system_prompt: str | None = "You are helpful.",
    persona: str | None = "Friendly assistant.",
    temperature: float = 0.7,
) -> dict:
    payload = {
        "name": name,
        "ai_model_id": ai_model_id,
        "temperature": temperature,
    }
    if system_prompt is not None:
        payload["system_prompt"] = system_prompt
    if persona is not None:
        payload["persona"] = persona
    resp = client.post("/agents", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def plan_generous(db: Session) -> Plan:
    p = Plan(
        code="generous_test",
        name="Generous Test",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        users_limit=10,
        pipelines_limit=10,
        integrations_limit=0,
        monthly_ai_credits=100000,
        monthly_conversations=5000,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def user_s(db: Session):
    return _make_user(db, "settings_user@test.com", "Settings User")


@pytest.fixture()
def workspace_s(db: Session, user_s):
    return _make_workspace(db, user_s, "workspace-settings", "Settings Workspace")


@pytest.fixture()
def sub_s(db: Session, workspace_s, plan_generous: Plan) -> WorkspaceSubscription:
    return _make_subscription(db, workspace_s, plan_generous)


@pytest.fixture()
def model_s(db: Session):
    return _make_ai_model(db)


@pytest.fixture()
def client_s(db: Session, user_s, workspace_s, sub_s):
    with _make_client(db, user_s, workspace_s) as c:
        yield c


# ── create_agent: satellite records ──────────────────────────────────────────

def test_create_agent_creates_prompt_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(
        client_s, str(model_s.id),
        system_prompt="Be concise.",
        persona="Professional.",
    )
    agent_id = uuid.UUID(data["id"])
    ps = _get_prompt_settings(db, agent_id)

    assert ps is not None
    assert ps.system_prompt == "Be concise."
    assert ps.persona == "Professional."


def test_create_agent_creates_model_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id), temperature=0.5)
    agent_id = uuid.UUID(data["id"])
    ms = _get_model_settings(db, agent_id)

    assert ms is not None
    assert ms.ai_model_id == model_s.id
    assert ms.model_name == model_s.model_name
    assert float(ms.temperature) == pytest.approx(0.5)


def test_create_agent_prompt_settings_are_unique_per_agent(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id))
    agent_id = uuid.UUID(data["id"])
    count = db.scalar(
        select(func.count(AgentPromptSettings.id)).where(
            AgentPromptSettings.agent_id == agent_id
        )
    )
    assert count == 1


def test_create_agent_model_settings_are_unique_per_agent(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id))
    agent_id = uuid.UUID(data["id"])
    count = db.scalar(
        select(func.count(AgentModelSettings.id)).where(
            AgentModelSettings.agent_id == agent_id
        )
    )
    assert count == 1


# ── AgentOut sourced from satellites ─────────────────────────────────────────

def test_agent_out_includes_all_fields_from_satellites(db: Session, client_s, model_s):
    """AgentOut must return system_prompt, persona, ai_model_id, model_name, temperature."""
    data = _create_agent_via_api(
        client_s, str(model_s.id),
        system_prompt="Test prompt.",
        persona="Persona text.",
        temperature=0.3,
    )
    assert data["system_prompt"] == "Test prompt."
    assert data["persona"] == "Persona text."
    assert data["ai_model_id"] == str(model_s.id)
    assert data["model_name"] == model_s.model_name
    assert data["temperature"] == pytest.approx(0.3)


def test_get_agent_returns_fields_from_satellites(db: Session, client_s, model_s):
    created = _create_agent_via_api(client_s, str(model_s.id), system_prompt="Satellite check.")
    resp = client_s.get(f"/agents/{created['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["system_prompt"] == "Satellite check."
    assert data["ai_model_id"] == str(model_s.id)


def test_list_agents_returns_fields_from_satellites(db: Session, client_s, model_s):
    _create_agent_via_api(client_s, str(model_s.id), name="A1", system_prompt="Listed.")
    resp = client_s.get("/agents")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["system_prompt"] == "Listed."
    assert items[0]["ai_model_id"] == str(model_s.id)


# ── update_agent routes to correct satellite ──────────────────────────────────

def test_update_system_prompt_updates_prompt_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id), system_prompt="Original.")
    agent_id = uuid.UUID(data["id"])

    resp = client_s.patch(f"/agents/{agent_id}", json={"system_prompt": "Updated prompt."})
    assert resp.status_code == 200

    ps = _get_prompt_settings(db, agent_id)
    assert ps.system_prompt == "Updated prompt."
    # Response also reflects new value
    assert resp.json()["system_prompt"] == "Updated prompt."


def test_update_persona_updates_prompt_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id), persona="Old persona.")
    agent_id = uuid.UUID(data["id"])

    resp = client_s.patch(f"/agents/{agent_id}", json={"persona": "New persona."})
    assert resp.status_code == 200

    ps = _get_prompt_settings(db, agent_id)
    assert ps.persona == "New persona."


def test_update_ai_model_id_updates_model_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id))
    agent_id = uuid.UUID(data["id"])

    model2 = _make_ai_model(db)
    resp = client_s.patch(f"/agents/{agent_id}", json={"ai_model_id": str(model2.id)})
    assert resp.status_code == 200

    ms = _get_model_settings(db, agent_id)
    assert ms.ai_model_id == model2.id
    assert ms.model_name == model2.model_name
    assert resp.json()["ai_model_id"] == str(model2.id)
    assert resp.json()["model_name"] == model2.model_name


def test_update_temperature_updates_model_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id), temperature=0.7)
    agent_id = uuid.UUID(data["id"])

    resp = client_s.patch(f"/agents/{agent_id}", json={"temperature": 0.2})
    assert resp.status_code == 200

    ms = _get_model_settings(db, agent_id)
    assert float(ms.temperature) == pytest.approx(0.2)
    assert resp.json()["temperature"] == pytest.approx(0.2)


def test_clear_persona_clears_prompt_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id), persona="Has persona.")
    agent_id = uuid.UUID(data["id"])

    resp = client_s.patch(f"/agents/{agent_id}", json={"persona": None})
    assert resp.status_code == 200

    ps = _get_prompt_settings(db, agent_id)
    assert ps.persona is None
    assert resp.json()["persona"] is None


def test_update_name_does_not_touch_settings(db: Session, client_s, model_s):
    data = _create_agent_via_api(
        client_s, str(model_s.id),
        name="Old Name", system_prompt="Keep this."
    )
    agent_id = uuid.UUID(data["id"])

    resp = client_s.patch(f"/agents/{agent_id}", json={"name": "New Name"})
    assert resp.status_code == 200

    ps = _get_prompt_settings(db, agent_id)
    assert ps.system_prompt == "Keep this."
    assert resp.json()["name"] == "New Name"


# ── transition: parallel write to agents.* ───────────────────────────────────

def test_create_agent_writes_legacy_fields_for_transition(db: Session, client_s, model_s):
    """During transition, agents.* must also be updated (for rollback safety)."""
    data = _create_agent_via_api(
        client_s, str(model_s.id),
        system_prompt="Legacy too.", persona="P.", temperature=0.4
    )
    agent_id = uuid.UUID(data["id"])

    agent = db.scalar(select(Agent).where(Agent.id == agent_id))
    assert agent.system_prompt == "Legacy too."
    assert agent.persona == "P."
    assert float(agent.temperature) == pytest.approx(0.4)
    assert agent.ai_model_id == model_s.id
    assert agent.model_name == model_s.model_name


def test_update_agent_writes_legacy_fields_for_transition(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id), system_prompt="Original.")
    agent_id = uuid.UUID(data["id"])

    client_s.patch(f"/agents/{agent_id}", json={"system_prompt": "Updated."})

    agent = db.scalar(select(Agent).where(Agent.id == agent_id))
    assert agent.system_prompt == "Updated."


# ── update_agent_status reads prompt from satellite ───────────────────────────

def test_activate_agent_reads_system_prompt_from_prompt_settings(
    db: Session, client_s, model_s
):
    data = _create_agent_via_api(client_s, str(model_s.id), system_prompt="Required prompt.")
    agent_id = data["id"]

    resp = client_s.patch(f"/agents/{agent_id}/status", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_activate_agent_fails_when_prompt_settings_has_no_system_prompt(
    db: Session, client_s, model_s
):
    data = _create_agent_via_api(client_s, str(model_s.id), system_prompt=None)
    agent_id = data["id"]

    resp = client_s.patch(f"/agents/{agent_id}/status", json={"status": "active"})
    assert resp.status_code == 400
    assert "system_prompt" in resp.json()["detail"]


def test_activate_agent_after_clearing_prompt_fails(db: Session, client_s, model_s):
    data = _create_agent_via_api(client_s, str(model_s.id), system_prompt="Will be cleared.")
    agent_id = data["id"]

    # Clear system_prompt via PATCH
    resp = client_s.patch(f"/agents/{agent_id}", json={"system_prompt": None})
    assert resp.status_code == 200

    # Now activation must fail
    resp = client_s.patch(f"/agents/{agent_id}/status", json={"status": "active"})
    assert resp.status_code == 400


# ── on-demand creation (transition fallback) ─────────────────────────────────

def test_update_creates_prompt_settings_on_demand_if_missing(db: Session, client_s, model_s):
    """If prompt_settings is absent (pre-migration agent), update must create it on-demand."""
    # Create agent normally (settings are created)
    data = _create_agent_via_api(
        client_s, str(model_s.id), system_prompt="Before delete."
    )
    agent_id = uuid.UUID(data["id"])

    # Simulate pre-migration state by deleting the satellite record
    db.execute(
        delete(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent_id)
    )
    db.commit()

    assert _get_prompt_settings(db, agent_id) is None

    # PATCH should recreate the record from agent.* fields (fallback)
    resp = client_s.patch(f"/agents/{agent_id}", json={"system_prompt": "Recreated."})
    assert resp.status_code == 200

    ps = _get_prompt_settings(db, agent_id)
    assert ps is not None
    assert ps.system_prompt == "Recreated."


def test_update_creates_model_settings_on_demand_if_missing(db: Session, client_s, model_s):
    from sqlalchemy import delete

    data = _create_agent_via_api(client_s, str(model_s.id), temperature=0.7)
    agent_id = uuid.UUID(data["id"])

    db.execute(
        delete(AgentModelSettings).where(AgentModelSettings.agent_id == agent_id)
    )
    db.commit()

    model2 = _make_ai_model(db)
    resp = client_s.patch(f"/agents/{agent_id}", json={"ai_model_id": str(model2.id)})
    assert resp.status_code == 200

    ms = _get_model_settings(db, agent_id)
    assert ms is not None
    assert ms.ai_model_id == model2.id


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_prompt_settings_are_isolated_by_workspace(db: Session, plan_generous: Plan):
    """Settings of agent from workspace A must not be visible from workspace B."""
    user_x = _make_user(db, "x@test.com", "X")
    user_y = _make_user(db, "y@test.com", "Y")
    ws_x = _make_workspace(db, user_x, "ws-x-s", "WS X")
    ws_y = _make_workspace(db, user_y, "ws-y-s", "WS Y")
    _make_subscription(db, ws_x, plan_generous)
    _make_subscription(db, ws_y, plan_generous)
    model = _make_ai_model(db)

    with _make_client(db, user_x, ws_x) as cx:
        data = _create_agent_via_api(cx, str(model.id), system_prompt="Private prompt.")
        agent_id = data["id"]

    # Workspace B cannot see agent from workspace A
    with _make_client(db, user_y, ws_y) as cy:
        resp = cy.get(f"/agents/{agent_id}")
        assert resp.status_code == 404
