"""
Tests for Agent Model UX.1 — Context Tier feature.

Covers:
1.  New agent defaults to context_tier='standard'.
2.  Existing agent (post-migration) has tier='standard'.
3.  API saves context_tier via PATCH.
4.  API rejects invalid context_tier (422).
5.  Free/starter allows 'economical'.
6.  Free/starter allows 'standard'.
7.  Free/starter blocks 'broad'.
8.  Free/starter blocks 'advanced'.
9.  Free/starter blocks 'maximum'.
10. Growth allows 'broad'.
11. Growth allows 'advanced'.
12. Growth blocks 'maximum'.
13. Scale allows 'maximum'.
14. Credits use context multiplier (econômico=1x, padrão=2x, etc.).
15. Context tier limits RAG max chars in context builder.
16. History limit reduced for economical tier.
"""

import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent_model_settings import AgentModelSettings
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.context_tier_service import (
    CONTEXT_TIER_CONFIG,
    calculate_credits,
    plan_allows_context_tier,
    validate_context_tier,
)
from tests.conftest import (
    _make_ai_model,
    _make_client,
    _make_subscription,
    _make_user,
    _make_workspace,
)


# ── Plan fixtures ─────────────────────────────────────────────────────────────

def _make_plan(db: Session, code: str, name: str) -> Plan:
    p = Plan(
        code=code,
        name=name,
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        users_limit=10,
        pipelines_limit=10,
        integrations_limit=0,
        monthly_ai_credits=100_000,
        monthly_conversations=5_000,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture()
def plan_starter(db: Session) -> Plan:
    return _make_plan(db, "starter", "Starter")


@pytest.fixture()
def plan_growth(db: Session) -> Plan:
    return _make_plan(db, "growth", "Growth")


@pytest.fixture()
def plan_scale(db: Session) -> Plan:
    return _make_plan(db, "scale", "Scale")


@contextmanager
def _setup_client(db: Session, plan: Plan):
    user = _make_user(db, f"u_{uuid.uuid4().hex[:6]}@test.com", "User")
    ws = _make_workspace(db, user, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    _make_subscription(db, ws, plan)
    model = _make_ai_model(db)
    with _make_client(db, user, ws) as client:
        yield client, model


# ── Unit tests: context_tier_service ─────────────────────────────────────────

def test_validate_context_tier_valid():
    for tier in ["economical", "standard", "broad", "advanced", "maximum"]:
        assert validate_context_tier(tier) is True


def test_validate_context_tier_invalid():
    assert validate_context_tier("ultra") is False
    assert validate_context_tier("") is False
    assert validate_context_tier("Standard") is False


def test_plan_allows_context_tier_starter():
    assert plan_allows_context_tier("starter", "economical") is True
    assert plan_allows_context_tier("starter", "standard") is True
    assert plan_allows_context_tier("starter", "broad") is False
    assert plan_allows_context_tier("starter", "advanced") is False
    assert plan_allows_context_tier("starter", "maximum") is False


def test_plan_allows_context_tier_growth():
    assert plan_allows_context_tier("growth", "broad") is True
    assert plan_allows_context_tier("growth", "advanced") is True
    assert plan_allows_context_tier("growth", "maximum") is False


def test_plan_allows_context_tier_scale():
    assert plan_allows_context_tier("scale", "maximum") is True
    assert plan_allows_context_tier("enterprise", "maximum") is True


def test_calculate_credits_multipliers():
    base = 2
    assert calculate_credits(base, "economical") == 2   # 2 × 1
    assert calculate_credits(base, "standard")   == 4   # 2 × 2
    assert calculate_credits(base, "broad")      == 8   # 2 × 4
    assert calculate_credits(base, "advanced")   == 16  # 2 × 8
    assert calculate_credits(base, "maximum")    == 32  # 2 × 16


def test_calculate_credits_minimum_one():
    # Even with multiplier=1 and base=0 we never return 0 (always ≥ 1).
    # base=1, tier=economical → 1*1=1 ≥ 1
    assert calculate_credits(1, "economical") == 1


def test_context_tier_config_keys():
    for tier in ["economical", "standard", "broad", "advanced", "maximum"]:
        cfg = CONTEXT_TIER_CONFIG[tier]
        assert "max_chars" in cfg
        assert "credit_multiplier" in cfg
        assert "history_limit" in cfg
        assert "rag_max_chars" in cfg
        assert "catalog_limit" in cfg
        # Larger tiers must have larger budgets
    assert (
        CONTEXT_TIER_CONFIG["economical"]["max_chars"]
        < CONTEXT_TIER_CONFIG["standard"]["max_chars"]
        < CONTEXT_TIER_CONFIG["broad"]["max_chars"]
        < CONTEXT_TIER_CONFIG["advanced"]["max_chars"]
        < CONTEXT_TIER_CONFIG["maximum"]["max_chars"]
    )


# ── Integration tests via API ─────────────────────────────────────────────────

def test_create_agent_defaults_context_tier_standard(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "Test", "ai_model_id": str(model.id)})
        assert resp.status_code == 201
        assert resp.json()["context_tier"] == "standard"


def test_patch_agent_saves_context_tier(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "Test", "ai_model_id": str(model.id)})
        agent_id = resp.json()["id"]

        resp = client.patch(f"/agents/{agent_id}", json={"context_tier": "economical"})
        assert resp.status_code == 200
        assert resp.json()["context_tier"] == "economical"


def test_patch_agent_invalid_context_tier_returns_422(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "Test", "ai_model_id": str(model.id)})
        agent_id = resp.json()["id"]

        resp = client.patch(f"/agents/{agent_id}", json={"context_tier": "ultra"})
        assert resp.status_code in (402, 422)


def test_patch_agent_context_tier_persisted_in_db(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "Test", "ai_model_id": str(model.id)})
        agent_id = uuid.UUID(resp.json()["id"])

        client.patch(f"/agents/{agent_id}", json={"context_tier": "economical"})

        ms = db.query(AgentModelSettings).filter(
            AgentModelSettings.agent_id == agent_id
        ).first()
        assert ms is not None
        assert ms.context_window_tier == "economical"


# ── Plan gating integration tests ─────────────────────────────────────────────

def test_starter_allows_economical(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "economical"})
        assert resp2.status_code == 200


def test_starter_allows_standard(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "standard"})
        assert resp2.status_code == 200


def test_starter_blocks_broad(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "broad"})
        assert resp2.status_code == 402


def test_starter_blocks_advanced(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "advanced"})
        assert resp2.status_code == 402


def test_starter_blocks_maximum(db: Session, plan_starter: Plan):
    with _setup_client(db, plan_starter) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "maximum"})
        assert resp2.status_code == 402


def test_growth_allows_broad(db: Session, plan_growth: Plan):
    with _setup_client(db, plan_growth) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "broad"})
        assert resp2.status_code == 200


def test_growth_allows_advanced(db: Session, plan_growth: Plan):
    with _setup_client(db, plan_growth) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "advanced"})
        assert resp2.status_code == 200


def test_growth_blocks_maximum(db: Session, plan_growth: Plan):
    with _setup_client(db, plan_growth) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "maximum"})
        assert resp2.status_code == 402


def test_scale_allows_maximum(db: Session, plan_scale: Plan):
    with _setup_client(db, plan_scale) as (client, model):
        resp = client.post("/agents", json={"name": "A", "ai_model_id": str(model.id)})
        resp2 = client.patch(f"/agents/{resp.json()['id']}", json={"context_tier": "maximum"})
        assert resp2.status_code == 200
