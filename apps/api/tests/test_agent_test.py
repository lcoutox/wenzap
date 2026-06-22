"""
Tests for POST /agents/{agent_id}/test — Agent Playground endpoint.

LLM policy:
  All tests mock `app.llm.client.complete` so the Anthropic API is never called.
  Only the service orchestration, validations, credit accounting, and log behavior
  are tested here. Provider-level tests (rate limits, timeouts, auth errors) are
  the responsibility of app/llm/providers/anthropic.py unit tests (future).

Log policy:
  Only executions that reached the LLM provider are recorded in agent_test_runs.
  Executions blocked before the LLM call do NOT create log entries — tests verify
  this explicitly in the "bloqueios antes da LLM" group.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.llm.schemas import LLMProviderError, LLMResponse
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.agent_test_run import AgentTestRun
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace_member import WorkspaceMember
from tests.conftest import (
    _make_client,
    _make_subscription,
    _make_user,
    _make_workspace,
)

# ── Constants ─────────────────────────────────────────────────────────────────

_VALID_ANTHROPIC_MODEL_NAME = "claude-sonnet-4-6"
_VALID_MESSAGE = "Hello, can you help me?"

# ── Mock LLM response ─────────────────────────────────────────────────────────

def _mock_llm_response(content: str = "I'm here to help!") -> LLMResponse:
    return LLMResponse(
        content=content,
        input_tokens=120,
        output_tokens=80,
        duration_ms=850,
    )

# ── DB factories ──────────────────────────────────────────────────────────────

def _make_plan(
    db: Session,
    *,
    monthly_ai_credits: int = 10_000,
    code: str | None = None,
    min_plan_code: str = "starter",
) -> Plan:
    p = Plan(
        code=code or f"plan_{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=5,
        users_limit=10,
        pipelines_limit=5,
        integrations_limit=5,
        monthly_ai_credits=monthly_ai_credits,
        monthly_conversations=5000,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_anthropic_provider(db: Session, *, is_active: bool = True) -> AiModelProvider:
    p = AiModelProvider(
        id=uuid.uuid4(),
        code="anthropic",
        name="Anthropic",
        is_active=is_active,
    )
    db.add(p)
    db.flush()
    return p


def _make_nexbrain_provider(db: Session, *, is_active: bool = True) -> AiModelProvider:
    p = AiModelProvider(
        id=uuid.uuid4(),
        code="nexbrain",
        name="Nexbrain",
        is_active=is_active,
    )
    db.add(p)
    db.flush()
    return p


def _make_provider(
    db: Session,
    *,
    code: str,
    is_active: bool = True,
) -> AiModelProvider:
    # Reuse existing provider with the same code within the same test transaction.
    existing = db.scalar(select(AiModelProvider).where(AiModelProvider.code == code))
    if existing is not None:
        if existing.is_active != is_active:
            existing.is_active = is_active
            db.flush()
        return existing
    p = AiModelProvider(
        id=uuid.uuid4(),
        code=code,
        name=code.capitalize(),
        is_active=is_active,
    )
    db.add(p)
    db.flush()
    return p


def _make_model(
    db: Session,
    provider: AiModelProvider,
    *,
    model_name: str = _VALID_ANTHROPIC_MODEL_NAME,
    min_plan_code: str = "starter",
    credits_per_message: int = 2,
    is_active: bool = True,
) -> AiModel:
    m = AiModel(
        id=uuid.uuid4(),
        provider_id=provider.id,
        code=f"model-{uuid.uuid4().hex[:8]}",
        display_name="Claude Sonnet",
        model_name=model_name,
        credits_per_message=credits_per_message,
        min_plan_code=min_plan_code,
        is_active=is_active,
        sort_order=1,
    )
    db.add(m)
    db.flush()
    return m


def _make_usage_counter(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    ai_credits_used: int = 0,
    period_days: int = 30,
) -> UsageCounter:
    now = datetime.now(timezone.utc)
    c = UsageCounter(
        workspace_id=workspace_id,
        period_start=now - timedelta(hours=1),
        period_end=now + timedelta(days=period_days),
        ai_credits_used=ai_credits_used,
        conversations_count=0,
        messages_count=0,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_agent(
    db: Session,
    workspace_id: uuid.UUID,
    model: AiModel,
    *,
    name: str = "Test Agent",
    description: str | None = "Helps with things.",
    status: str = "active",
    system_prompt: str | None = "You are a helpful assistant.",
    persona: str | None = "Friendly and concise.",
    temperature: float = 0.7,
) -> Agent:
    agent = Agent(
        workspace_id=workspace_id,
        name=name,
        description=description,
        status=status,
        ai_model_id=model.id,
        model_name=model.model_name,
        temperature=temperature,
    )
    db.add(agent)
    db.flush()

    ps = AgentPromptSettings(
        agent_id=agent.id,
        system_prompt=system_prompt,
        persona=persona,
    )
    db.add(ps)

    ms = AgentModelSettings(
        agent_id=agent.id,
        ai_model_id=model.id,
        model_name=model.model_name,
        temperature=temperature,
    )
    db.add(ms)

    db.commit()
    db.refresh(agent)
    return agent


def _full_setup(
    db: Session,
    *,
    monthly_ai_credits: int = 10_000,
    ai_credits_used: int = 0,
    system_prompt: str | None = "You are a helpful assistant.",
    agent_status: str = "active",
    persona: str | None = "Friendly and concise.",
    model_name: str = _VALID_ANTHROPIC_MODEL_NAME,
    min_plan_code: str = "starter",
    credits_per_message: int = 2,
    provider_code: str = "anthropic",
    provider_active: bool = True,
    model_active: bool = True,
):
    """
    Creates a complete, valid setup:
      user → workspace → plan → subscription → provider → model → agent
      → usage_counter

    Returns (user, workspace, agent, model, provider, counter).
    """
    user = _make_user(db, f"{uuid.uuid4().hex[:6]}@test.com", "Test User")
    ws = _make_workspace(db, user, f"ws-{uuid.uuid4().hex[:6]}", "Test WS")
    plan = _make_plan(db, monthly_ai_credits=monthly_ai_credits, min_plan_code=min_plan_code)
    _make_subscription(db, ws, plan)
    provider = _make_provider(db, code=provider_code, is_active=provider_active)
    model = _make_model(
        db,
        provider,
        model_name=model_name,
        min_plan_code=min_plan_code,
        credits_per_message=credits_per_message,
        is_active=model_active,
    )
    agent = _make_agent(
        db,
        ws.id,
        model,
        status=agent_status,
        system_prompt=system_prompt,
        persona=persona,
    )
    counter = _make_usage_counter(db, ws.id, ai_credits_used=ai_credits_used)
    return user, ws, agent, model, provider, counter


def _post_test(client, agent_id, *, message: str = _VALID_MESSAGE):
    return client.post(f"/agents/{agent_id}/test", json={"message": message})


def _count_runs(db: Session, agent_id: uuid.UUID) -> int:
    return db.scalar(
        select(AgentTestRun).where(AgentTestRun.agent_id == agent_id).count() # type: ignore
    ) or db.query(AgentTestRun).filter(AgentTestRun.agent_id == agent_id).count()


def _get_runs(db: Session, agent_id: uuid.UUID) -> list[AgentTestRun]:
    return list(db.scalars(
        select(AgentTestRun).where(AgentTestRun.agent_id == agent_id)
    ).all())


def _get_counter(db: Session, workspace_id: uuid.UUID) -> UsageCounter | None:
    now = datetime.now(timezone.utc)
    return db.scalar(
        select(UsageCounter).where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.period_start <= now,
            UsageCounter.period_end >= now,
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Autorização / RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_viewer_cannot_test_agent(db):
    user, ws, agent, *_ = _full_setup(db)
    viewer = _make_user(db, f"viewer-{uuid.uuid4().hex[:6]}@test.com", "Viewer")
    db.add(WorkspaceMember(
        workspace_id=ws.id, user_id=viewer.id,
        role=MemberRole.viewer, status=MemberStatus.active,
    ))
    db.commit()

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, viewer, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 403


def test_member_can_test_agent(db):
    user, ws, agent, *_ = _full_setup(db)
    member = _make_user(db, f"member-{uuid.uuid4().hex[:6]}@test.com", "Member")
    db.add(WorkspaceMember(
        workspace_id=ws.id, user_id=member.id,
        role=MemberRole.member, status=MemberStatus.active,
    ))
    db.commit()

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, member, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200


def test_admin_can_test_agent(db):
    user, ws, agent, *_ = _full_setup(db)
    admin = _make_user(db, f"admin-{uuid.uuid4().hex[:6]}@test.com", "Admin")
    db.add(WorkspaceMember(
        workspace_id=ws.id, user_id=admin.id,
        role=MemberRole.admin, status=MemberStatus.active,
    ))
    db.commit()

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, admin, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200


def test_owner_can_test_agent(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200


def test_inactive_member_cannot_test_agent(db):
    user, ws, agent, *_ = _full_setup(db)
    inactive = _make_user(db, f"inactive-{uuid.uuid4().hex[:6]}@test.com", "Inactive")
    db.add(WorkspaceMember(
        workspace_id=ws.id, user_id=inactive.id,
        role=MemberRole.member, status=MemberStatus.inactive,
    ))
    db.commit()

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, inactive, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 403


def test_agent_from_other_workspace_returns_404(db):
    user_a, ws_a, agent_a, *_ = _full_setup(db)
    user_b, ws_b, *_ = _full_setup(db)

    # user_b tries to test an agent that belongs to ws_a
    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user_b, ws_b) as client:
            r = _post_test(client, agent_a.id)
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Status do agente
# ═══════════════════════════════════════════════════════════════════════════════

def test_archived_agent_cannot_be_tested(db):
    user, ws, agent, *_ = _full_setup(db, agent_status="archived")

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 400
    assert "archived" in r.json()["detail"].lower()


def test_draft_agent_with_system_prompt_can_be_tested(db):
    user, ws, agent, *_ = _full_setup(db, agent_status="draft")

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200


def test_draft_agent_without_system_prompt_returns_400(db):
    user, ws, agent, *_ = _full_setup(db, agent_status="draft", system_prompt=None)

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 400
    mock_llm.assert_not_called()


def test_active_agent_with_system_prompt_can_be_tested(db):
    user, ws, agent, *_ = _full_setup(db, agent_status="active")

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200


def test_inactive_agent_with_system_prompt_can_be_tested(db):
    user, ws, agent, *_ = _full_setup(db, agent_status="inactive")

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Validação da mensagem
# ═══════════════════════════════════════════════════════════════════════════════

def test_empty_message_returns_422(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = client.post(f"/agents/{agent.id}/test", json={"message": ""})
    assert r.status_code == 422
    mock_llm.assert_not_called()


def test_whitespace_only_message_returns_422(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = client.post(f"/agents/{agent.id}/test", json={"message": "   "})
    assert r.status_code == 422
    mock_llm.assert_not_called()


def test_message_too_long_returns_422(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = client.post(f"/agents/{agent.id}/test", json={"message": "x" * 4001})
    assert r.status_code == 422
    mock_llm.assert_not_called()


def test_valid_message_returns_200(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id, message="Tell me about your capabilities.")
    assert r.status_code == 200


def test_message_at_max_length_returns_200(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id, message="x" * 4000)
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Runtime / modelo
# ═══════════════════════════════════════════════════════════════════════════════

def test_anthropic_model_executes(db):
    user, ws, agent, *_ = _full_setup(db, provider_code="anthropic", model_name="claude-sonnet-4-6")

    with patch("app.llm.client.complete", return_value=_mock_llm_response()) as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200
    mock_llm.assert_called_once()


def test_nexbrain_model_with_anthropic_model_name_executes(db):
    user, ws, agent, *_ = _full_setup(
        db, provider_code="nexbrain", model_name="claude-sonnet-4-6"
    )

    with patch("app.llm.client.complete", return_value=_mock_llm_response()) as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200
    mock_llm.assert_called_once()


def test_openai_provider_returns_400(db):
    user, ws, agent, *_ = _full_setup(db, provider_code="openai", model_name="gpt-4o")

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 400
    mock_llm.assert_not_called()


def test_google_provider_returns_400(db):
    user, ws, agent, *_ = _full_setup(db, provider_code="google", model_name="gemini-2.0-flash")

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 400
    mock_llm.assert_not_called()


def test_inactive_provider_returns_error(db):
    user, ws, agent, *_ = _full_setup(db, provider_active=False)

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 400
    mock_llm.assert_not_called()


def test_inactive_model_returns_error(db):
    user, ws, agent, *_ = _full_setup(db, model_active=False)

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 404
    mock_llm.assert_not_called()


def test_anthropic_model_with_unsupported_model_name_returns_400(db):
    # provider=anthropic but model_name is NOT in the ANTHROPIC_EXECUTABLE_MODELS whitelist
    user, ws, agent, *_ = _full_setup(
        db, provider_code="anthropic", model_name="claude-2-legacy-not-supported"
    )

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 400
    mock_llm.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Plano / model availability
# ═══════════════════════════════════════════════════════════════════════════════

def test_model_outside_plan_tier_returns_402(db):
    # model requires "scale", but workspace is on "starter"
    user, ws, agent, *_ = _full_setup(db, min_plan_code="scale")

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 402
    mock_llm.assert_not_called()


def test_model_within_plan_tier_executes(db):
    # model requires "starter", workspace is on "starter" — allowed
    user, ws, agent, *_ = _full_setup(db, min_plan_code="starter")

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Créditos
# ═══════════════════════════════════════════════════════════════════════════════

def test_insufficient_credits_returns_402(db):
    # credits_per_message=2, used=9999, limit=10000 → 9999+2 > 10000
    user, ws, agent, *_ = _full_setup(
        db,
        monthly_ai_credits=10_000,
        ai_credits_used=9_999,
        credits_per_message=2,
    )

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 402
    mock_llm.assert_not_called()


def test_insufficient_credits_does_not_call_llm(db):
    user, ws, agent, *_ = _full_setup(
        db, monthly_ai_credits=1, ai_credits_used=1, credits_per_message=1
    )

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)
    mock_llm.assert_not_called()


def test_sufficient_credits_calls_llm(db):
    user, ws, agent, *_ = _full_setup(
        db, monthly_ai_credits=10_000, ai_credits_used=0, credits_per_message=2
    )

    with patch("app.llm.client.complete", return_value=_mock_llm_response()) as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200
    mock_llm.assert_called_once()


def test_success_increments_usage_counter(db):
    user, ws, agent, model, _, counter = _full_setup(
        db, monthly_ai_credits=10_000, ai_credits_used=100, credits_per_message=2
    )

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200

    db.expire(counter)
    updated = _get_counter(db, ws.id)
    assert updated is not None
    assert updated.ai_credits_used == 102  # 100 + 2


def test_response_credits_used_equals_model_credits_per_message(db):
    user, ws, agent, model, *_ = _full_setup(db, credits_per_message=5)

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200
    assert r.json()["credits_used"] == 5


def test_provider_error_does_not_consume_credits(db):
    user, ws, agent, _, __, counter = _full_setup(
        db, monthly_ai_credits=10_000, ai_credits_used=100, credits_per_message=2
    )

    with patch("app.llm.client.complete", side_effect=LLMProviderError("timeout")):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 503

    db.expire(counter)
    updated = _get_counter(db, ws.id)
    assert updated.ai_credits_used == 100  # unchanged


def test_missing_usage_counter_returns_402(db):
    user = _make_user(db, f"noctr-{uuid.uuid4().hex[:6]}@test.com", "No Counter")
    ws = _make_workspace(db, user, f"noctr-{uuid.uuid4().hex[:6]}", "No Counter WS")
    plan = _make_plan(db, monthly_ai_credits=10_000)
    _make_subscription(db, ws, plan)
    provider = _make_anthropic_provider(db)
    model = _make_model(db, provider)
    agent = _make_agent(db, ws.id, model)
    # Deliberately NO usage counter created

    with patch("app.llm.client.complete") as mock_llm:
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 402
    mock_llm.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Logs / metadados (agent_test_runs)
# ═══════════════════════════════════════════════════════════════════════════════

def test_success_creates_agent_test_run(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 200

    runs = _get_runs(db, agent.id)
    assert len(runs) == 1
    assert runs[0].status == "success"


def test_success_run_has_correct_metadata(db):
    user, ws, agent, model, provider, _ = _full_setup(db, credits_per_message=3)
    llm_resp = _mock_llm_response()

    with patch("app.llm.client.complete", return_value=llm_resp):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)

    run = _get_runs(db, agent.id)[0]
    assert run.workspace_id == ws.id
    assert run.agent_id == agent.id
    assert run.user_id == user.id
    assert run.ai_model_id == model.id
    assert run.provider_code == provider.code
    assert run.model_code == model.code
    assert run.model_name == model.model_name
    assert run.credits_used == 3
    assert run.input_tokens == llm_resp.input_tokens
    assert run.output_tokens == llm_resp.output_tokens
    assert run.duration_ms == llm_resp.duration_ms
    assert run.status == "success"
    assert run.error_message is None


def test_provider_error_creates_error_run(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", side_effect=LLMProviderError("Rate limit reached.")):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 503

    runs = _get_runs(db, agent.id)
    assert len(runs) == 1
    assert runs[0].status == "error"


def test_provider_error_run_has_sanitized_error_message(db):
    user, ws, agent, *_ = _full_setup(db)
    safe_msg = "Rate limit reached. Please try again in a few moments."

    with patch("app.llm.client.complete", side_effect=LLMProviderError(safe_msg)):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)

    run = _get_runs(db, agent.id)[0]
    assert run.error_message == safe_msg
    assert run.credits_used == 0
    assert run.input_tokens is None
    assert run.output_tokens is None


def test_provider_error_run_does_not_store_full_prompt(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", side_effect=LLMProviderError("error")):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id, message="My secret question")

    run = _get_runs(db, agent.id)[0]
    # The run must NOT store the user message or system prompt
    assert run.error_message is not None
    assert "My secret question" not in (run.error_message or "")


def test_block_before_llm_does_not_create_run(db):
    """Archived agent blocked before LLM → no agent_test_runs entry."""
    user, ws, agent, *_ = _full_setup(db, agent_status="archived")

    with patch("app.llm.client.complete"):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)

    runs = _get_runs(db, agent.id)
    assert len(runs) == 0


def test_block_insufficient_credits_does_not_create_run(db):
    user, ws, agent, *_ = _full_setup(
        db, monthly_ai_credits=1, ai_credits_used=1, credits_per_message=1
    )

    with patch("app.llm.client.complete"):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)

    runs = _get_runs(db, agent.id)
    assert len(runs) == 0


def test_block_missing_system_prompt_does_not_create_run(db):
    user, ws, agent, *_ = _full_setup(db, system_prompt=None)

    with patch("app.llm.client.complete"):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)

    runs = _get_runs(db, agent.id)
    assert len(runs) == 0


def test_block_unsupported_model_does_not_create_run(db):
    user, ws, agent, *_ = _full_setup(db, provider_code="openai", model_name="gpt-4o")

    with patch("app.llm.client.complete"):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)

    runs = _get_runs(db, agent.id)
    assert len(runs) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Provider errors
# ═══════════════════════════════════════════════════════════════════════════════

def test_llm_provider_error_returns_503(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", side_effect=LLMProviderError("Connection refused.")):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)
    assert r.status_code == 503


def test_llm_provider_error_response_has_safe_message(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", side_effect=LLMProviderError("sk-ant-secret")):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)

    body = r.json()
    assert "detail" in body
    # The API key must never appear in the response body
    assert "sk-ant-secret" not in body["detail"]


def test_llm_provider_error_response_has_no_stacktrace(db):
    user, ws, agent, *_ = _full_setup(db)

    with patch("app.llm.client.complete", side_effect=LLMProviderError("fail")):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)

    body = r.json()
    # Stacktrace indicators must not appear in the response
    assert "Traceback" not in str(body)
    assert "File \"" not in str(body)


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Context builder
# ═══════════════════════════════════════════════════════════════════════════════

def test_context_builder_includes_system_prompt():
    from app.services.agent_context_builder import build_system_prompt

    result = build_system_prompt(
        agent_name="Aria",
        agent_description=None,
        system_prompt="Always respond in Portuguese.",
        persona=None,
    )
    assert "Always respond in Portuguese." in result


def test_context_builder_includes_persona():
    from app.services.agent_context_builder import build_system_prompt

    result = build_system_prompt(
        agent_name="Aria",
        agent_description=None,
        system_prompt="You are an assistant.",
        persona="Formal and precise.",
    )
    assert "Formal and precise." in result


def test_context_builder_includes_agent_name():
    from app.services.agent_context_builder import build_system_prompt

    result = build_system_prompt(
        agent_name="SalesBot",
        agent_description=None,
        system_prompt="Help sell products.",
        persona=None,
    )
    assert "SalesBot" in result


def test_context_builder_includes_description_when_present():
    from app.services.agent_context_builder import build_system_prompt

    result = build_system_prompt(
        agent_name="Support",
        agent_description="Handles customer support queries.",
        system_prompt="Be helpful.",
        persona=None,
    )
    assert "Handles customer support queries." in result


def test_context_builder_omits_empty_persona():
    from app.services.agent_context_builder import build_system_prompt

    result = build_system_prompt(
        agent_name="Bot",
        agent_description=None,
        system_prompt="You are a bot.",
        persona="",
    )
    assert "Personality" not in result


def test_context_builder_no_rag_content():
    """Phase 3: context must not contain knowledge base or RAG references."""
    from app.services.agent_context_builder import build_system_prompt

    result = build_system_prompt(
        agent_name="Bot",
        agent_description="Does things.",
        system_prompt="You are a bot.",
        persona="Friendly.",
    )
    # These terms signal unintended RAG leakage in Phase 3
    assert "knowledge base" not in result.lower()
    assert "retrieved" not in result.lower()
    assert "context documents" not in result.lower()


def test_llm_is_called_with_system_prompt_in_request(db):
    """Integration: the LLM receives the built system prompt (includes agent name)."""
    user, ws, agent, *_ = _full_setup(db, system_prompt="Be helpful.")

    captured: list = []
    def capture(request):
        captured.append(request)
        return _mock_llm_response()

    with patch("app.llm.client.complete", side_effect=capture):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id)

    assert len(captured) == 1
    llm_req = captured[0]
    assert "Be helpful." in llm_req.system
    assert agent.name in llm_req.system


def test_llm_is_called_with_user_message(db):
    user, ws, agent, *_ = _full_setup(db)

    captured: list = []
    def capture(request):
        captured.append(request)
        return _mock_llm_response()

    with patch("app.llm.client.complete", side_effect=capture):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id, message="What can you do?")

    assert len(captured) == 1
    messages = captured[0].messages
    assert any(m.role == "user" and "What can you do?" in m.content for m in messages)


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Response shape
# ═══════════════════════════════════════════════════════════════════════════════

def test_success_response_shape(db):
    user, ws, agent, model, provider, _ = _full_setup(db, credits_per_message=2)
    llm_resp = _mock_llm_response("I'm here!")

    with patch("app.llm.client.complete", return_value=llm_resp):
        with _make_client(db, user, ws) as client:
            r = _post_test(client, agent.id)

    assert r.status_code == 200
    body = r.json()
    assert body["reply"] == "I'm here!"
    assert body["credits_used"] == 2
    assert body["input_tokens"] == llm_resp.input_tokens
    assert body["output_tokens"] == llm_resp.output_tokens
    assert body["duration_ms"] == llm_resp.duration_ms
    assert body["model"]["display_name"] == model.display_name
    assert body["model"]["provider"] == provider.code
    assert body["model"]["model_name"] == model.model_name
