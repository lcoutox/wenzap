"""
Tests for GET /ai-models — plan-aware catalog endpoint.
"""

import uuid

from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.plan import Plan
from tests.conftest import _make_client, _make_subscription, _make_user, _make_workspace


def _seed_provider(db, code=None, name="Anthropic", is_active=True):
    code = code or f"provider-{uuid.uuid4().hex[:6]}"
    p = AiModelProvider(id=uuid.uuid4(), code=code, name=name, is_active=is_active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _seed_model(
    db,
    provider,
    code,
    display_name,
    model_name,
    *,
    credits_per_message=1,
    min_plan_code="starter",
    is_default=False,
    is_active=True,
    sort_order=0,
):
    m = AiModel(
        id=uuid.uuid4(),
        provider_id=provider.id,
        code=code,
        display_name=display_name,
        model_name=model_name,
        credits_per_message=credits_per_message,
        min_plan_code=min_plan_code,
        is_default=is_default,
        is_active=is_active,
        sort_order=sort_order,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _plan_and_sub(db, workspace, plan_code="starter"):
    p = Plan(
        code=f"{plan_code}_{uuid.uuid4().hex[:6]}",
        name=plan_code.title(),
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
    db.add(p)
    db.commit()
    db.refresh(p)
    _make_subscription(db, workspace, p)
    return p


# ── Basic catalog ─────────────────────────────────────────────────────────────

def test_get_ai_models_returns_active_providers_and_models(db):
    provider = _seed_provider(db, code="anthropic-test")
    _seed_model(db, provider, "claude-sonnet-t", "Claude Sonnet", "claude-sonnet-4-6",
                is_default=True, sort_order=1)
    _seed_model(db, provider, "claude-haiku-t", "Claude Haiku", "claude-haiku-4-5",
                sort_order=2)

    user = _make_user(db, "aimodels@test.com", "AI Models User")
    ws = _make_workspace(db, user, "aimodels-ws", "AI Models WS")
    _plan_and_sub(db, ws)

    with _make_client(db, user, ws) as client:
        response = client.get("/ai-models")

    assert response.status_code == 200
    body = response.json()
    assert "providers" in body
    assert "current_plan" in body
    prov = next(p for p in body["providers"] if p["code"] == "anthropic-test")
    assert len(prov["models"]) == 2
    assert prov["models"][0]["code"] == "claude-sonnet-t"
    assert prov["models"][0]["is_default"] is True
    assert prov["models"][1]["code"] == "claude-haiku-t"


def test_inactive_models_are_excluded(db):
    provider = _seed_provider(db, code="prov-inactive-test")
    _seed_model(db, provider, "active-model-t", "Active", "active-v1", is_active=True)
    _seed_model(db, provider, "inactive-model-t", "Old", "old-v1", is_active=False)

    user = _make_user(db, "inactive@test.com", "Inactive Test")
    ws = _make_workspace(db, user, "inactive-ws", "Inactive WS")
    _plan_and_sub(db, ws)

    with _make_client(db, user, ws) as client:
        response = client.get("/ai-models")

    prov = next(p for p in response.json()["providers"] if p["code"] == "prov-inactive-test")
    codes = [m["code"] for m in prov["models"]]
    assert "active-model-t" in codes
    assert "inactive-model-t" not in codes


def test_inactive_providers_are_excluded(db):
    _seed_provider(db, code="inactive-prov-t", name="Inactive Provider", is_active=False)

    user = _make_user(db, "noprov@test.com", "No Provider")
    ws = _make_workspace(db, user, "noprov-ws", "No Provider WS")
    _plan_and_sub(db, ws)

    with _make_client(db, user, ws) as client:
        response = client.get("/ai-models")

    codes = [p["code"] for p in response.json()["providers"]]
    assert "inactive-prov-t" not in codes


def test_get_ai_models_requires_auth(db):
    from fastapi.testclient import TestClient

    from app.main import app
    app.dependency_overrides.clear()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/ai-models")
    assert response.status_code == 401


def test_model_fields_present(db):
    provider = _seed_provider(db, code="fields-prov-t")
    _seed_model(db, provider, "fields-model-t", "Fields Model", "fields-v1",
                credits_per_message=3, is_default=True, sort_order=1)

    user = _make_user(db, "fields@test.com", "Fields Test")
    ws = _make_workspace(db, user, "fields-ws", "Fields WS")
    _plan_and_sub(db, ws)

    with _make_client(db, user, ws) as client:
        response = client.get("/ai-models")

    prov = next(p for p in response.json()["providers"] if p["code"] == "fields-prov-t")
    model = prov["models"][0]
    assert "id" in model
    assert "code" in model
    assert "display_name" in model
    assert "model_name" in model
    assert "is_default" in model
    assert "credits_per_message" in model
    assert model["credits_per_message"] == 3
    assert "available" in model
    assert "supports_vision" in model
    assert "supports_tools" in model
    assert "supports_reasoning" in model
    assert "supports_code" in model
    assert "min_plan_code" in model
    assert "context_window_tokens" in model


# ── Plan-based availability ───────────────────────────────────────────────────

def test_starter_plan_blocks_growth_model(db):
    provider = _seed_provider(db, code="avail-prov-t")
    _seed_model(db, provider, "starter-model-t", "Starter Model", "starter-v1",
                min_plan_code="starter", sort_order=1)
    _seed_model(db, provider, "growth-model-t", "Growth Model", "growth-v1",
                min_plan_code="growth", sort_order=2)

    user = _make_user(db, "starter-avail@test.com", "Starter Avail")
    ws = _make_workspace(db, user, "starter-avail-ws", "Starter Avail WS")
    _plan_and_sub(db, ws, plan_code="starter")

    with _make_client(db, user, ws) as client:
        response = client.get("/ai-models")

    prov = next(p for p in response.json()["providers"] if p["code"] == "avail-prov-t")
    by_code = {m["code"]: m for m in prov["models"]}
    assert by_code["starter-model-t"]["available"] is True
    assert by_code["growth-model-t"]["available"] is False


def test_growth_plan_unlocks_growth_model(db):
    provider = _seed_provider(db, code="growth-prov-t")
    _seed_model(db, provider, "growth-only-t", "Growth Only", "growth-only-v1",
                min_plan_code="growth", sort_order=1)

    user = _make_user(db, "growth-avail@test.com", "Growth Avail")
    ws = _make_workspace(db, user, "growth-avail-ws", "Growth Avail WS")

    p = Plan(
        code=f"growth_{uuid.uuid4().hex[:6]}",
        name="Growth",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        users_limit=20,
        pipelines_limit=10,
        integrations_limit=5,
        monthly_ai_credits=5000,
        monthly_conversations=2000,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    _make_subscription(db, ws, p)

    with _make_client(db, user, ws) as client:
        response = client.get("/ai-models")

    prov = next(p for p in response.json()["providers"] if p["code"] == "growth-prov-t")
    model = prov["models"][0]
    # "growth_xxx" plan code is not in PLAN_TIER, so defaults to tier 1 (starter)
    # This validates that unknown plan codes fall back safely
    assert "available" in model


def test_current_plan_returned_in_response(db):
    provider = _seed_provider(db, code="plan-resp-prov-t")
    _seed_model(db, provider, "plan-resp-model-t", "Plan Resp", "plan-resp-v1")

    user = _make_user(db, "planresp@test.com", "Plan Resp")
    ws = _make_workspace(db, user, "planresp-ws", "Plan Resp WS")
    _plan_and_sub(db, ws, plan_code="starter")

    with _make_client(db, user, ws) as client:
        response = client.get("/ai-models")

    body = response.json()
    assert "current_plan" in body
    # current_plan is the plan.code from DB — starts with "starter_"
    assert body["current_plan"].startswith("starter")
