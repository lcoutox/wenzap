"""
Agent Playground — test execution service.

Orchestrates the full flow for POST /agents/{agent_id}/test.

Session policy (Phase 3.1):
  Every test run is associated with a playground session.
  If session_id is provided, the existing session is used (after ownership
  validation). Otherwise a new session is created automatically.
  Session and message persistence are part of the same DB transaction as
  credit increment and agent_test_run insert.

Log policy (Phase 3):
  Only executions that actually reached the LLM provider are recorded in
  agent_test_runs. Executions blocked before the LLM call (insufficient
  credits, unsupported model, wrong agent status, plan limit) are NOT logged.
  This keeps the table as a clean audit of provider interactions, not
  validation failures.

Credit policy:
  Credits are checked before the LLM call. Increments happen ONLY on success,
  in the same DB transaction as the agent_test_runs INSERT and the assistant
  message to prevent partial accounting.

  The increment uses an atomic UPDATE (no read-before-write) to avoid race
  conditions when multiple requests run concurrently.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.llm import client as llm_client
from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.agent_test_run import AgentTestRun
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.agent_test import AgentTestModelInfo, AgentTestRequest, AgentTestResponse
from app.services import playground_service
from app.services.agent_context_builder import build_system_prompt
from app.services.ai_model_service import PLAN_TIER

# Phase 3: only these Anthropic model_name values can be executed.
# Both provider=anthropic and provider=nexbrain models are allowed
# if their model_name is in this set (nexbrain wraps Anthropic models).
ANTHROPIC_EXECUTABLE_MODELS: set[str] = {
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
}


def run_agent_test(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    data: AgentTestRequest,
) -> AgentTestResponse:
    # ── Pre-LLM validations (no DB writes) ───────────────────────────────────
    agent = _get_agent_or_404(db, workspace_id, agent_id)
    _validate_agent_testable(agent)
    model_settings = _get_model_settings_or_400(db, agent)
    model, provider = _get_model_and_provider(db, model_settings)
    _validate_model_active(model, provider)
    plan_code = _get_workspace_plan_code(db, workspace_id)
    _validate_plan(plan_code, model)
    _validate_runtime_support(model, provider)
    credits_needed = model.credits_per_message
    counter = _get_usage_counter_or_402(db, workspace_id)
    _validate_credits(counter, credits_needed, plan_code, db)

    # Validate session ownership before any writes — bad session_id must never
    # cause partial state (session created without messages).
    if data.session_id is not None:
        playground_service.get_session_or_404(db, workspace_id, agent_id, data.session_id)

    # ── Resolve or create session (all validations passed) ────────────────────
    if data.session_id is not None:
        session = playground_service.get_session_or_404(
            db, workspace_id, agent_id, data.session_id
        )
    else:
        session = playground_service.create_session_pending(
            db, workspace_id, agent_id, user_id
        )
        # Flush the new session row so its PK exists in the DB before the
        # message FK is checked on the next autoflush.
        db.flush()

    # ── Persist user message & update session metadata ────────────────────────
    playground_service.save_user_message(db, session.id, data.message)
    playground_service.update_session_title_from_first_message(db, session, data.message)
    playground_service.touch_session(db, session)

    # Flush so pending objects get PKs; LLM call happens outside the transaction.
    db.flush()

    # ── Build prompt & call LLM ───────────────────────────────────────────────
    prompt_settings = _get_prompt_settings(db, agent)
    system = build_system_prompt(
        agent_name=agent.name,
        agent_description=agent.description,
        system_prompt=prompt_settings.system_prompt,
        persona=prompt_settings.persona,
    )

    request = LLMRequest(
        model_name=model.model_name,
        system=system,
        messages=[LLMMessage(role="user", content=data.message)],
        temperature=float(model_settings.temperature),
    )

    try:
        llm_response = llm_client.complete(request)
    except LLMProviderError as exc:
        # Error path — user message + run error committed together, no credits consumed.
        _log_run(
            db,
            workspace_id=workspace_id,
            agent_id=agent_id,
            user_id=user_id,
            model=model,
            provider=provider,
            status="error",
            error_message=str(exc.message)[:500],
            credits_used=0,
            input_tokens=None,
            output_tokens=None,
            duration_ms=None,
        )
        playground_service.touch_session(db, session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error connecting to the model. Please try again.",
        )

    # ── Success: credits + run + assistant message in one transaction ─────────
    _increment_credits(db, workspace_id, credits_needed)
    run = _log_run(
        db,
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        model=model,
        provider=provider,
        status="success",
        error_message=None,
        credits_used=credits_needed,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
        duration_ms=llm_response.duration_ms,
    )
    db.flush()  # get run.id before using it as FK in the assistant message
    playground_service.save_assistant_message(
        db, session.id, llm_response.content, run.id
    )
    playground_service.touch_session(db, session)
    db.commit()

    return AgentTestResponse(
        reply=llm_response.content,
        credits_used=credits_needed,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
        duration_ms=llm_response.duration_ms,
        model=AgentTestModelInfo(
            display_name=model.display_name,
            provider=provider.code,
            model_name=model.model_name,
        ),
        session_id=session.id,
    )


# ── Internal helpers ─────────────────────────────────────────────────────────

def _get_agent_or_404(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
    agent = db.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    return agent


def _validate_agent_testable(agent: Agent) -> None:
    if agent.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archived agents cannot be tested.",
        )


def _get_prompt_settings(db: Session, agent: Agent) -> AgentPromptSettings:
    ps = db.scalar(
        select(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent.id)
    )
    # Fallback to agent columns for agents created before Phase 2.4
    if ps is None:
        system_prompt = agent.system_prompt or ""
        persona = agent.persona
    else:
        system_prompt = ps.system_prompt or ""
        persona = ps.persona

    effective_prompt = system_prompt.strip()
    if not effective_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A system_prompt is required to test this agent.",
        )

    if ps is not None:
        return ps

    stub = AgentPromptSettings.__new__(AgentPromptSettings)
    stub.system_prompt = system_prompt
    stub.persona = persona
    return stub


def _get_model_settings_or_400(db: Session, agent: Agent) -> AgentModelSettings:
    ms = db.scalar(
        select(AgentModelSettings).where(AgentModelSettings.agent_id == agent.id)
    )
    if ms is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This agent has no model configured. Select a model in Settings → Modelo.",
        )
    return ms


def _get_model_and_provider(
    db: Session, ms: AgentModelSettings
) -> tuple[AiModel, AiModelProvider]:
    model = db.scalar(select(AiModel).where(AiModel.id == ms.ai_model_id))
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Configured model not found."
        )
    provider = db.scalar(
        select(AiModelProvider).where(AiModelProvider.id == model.provider_id)
    )
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Model provider not found."
        )
    return model, provider


def _validate_model_active(model: AiModel, provider: AiModelProvider) -> None:
    if not model.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AI model not found or inactive."
        )
    if not provider.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The provider for this model is currently unavailable.",
        )


def _validate_plan(plan_code: str, model: AiModel) -> None:
    workspace_tier = PLAN_TIER.get(plan_code, 1)
    model_tier = PLAN_TIER.get(model.min_plan_code, 1)
    if workspace_tier < model_tier:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Model '{model.display_name}' requires the "
                f"'{model.min_plan_code}' plan or higher."
            ),
        )


def _validate_runtime_support(model: AiModel, provider: AiModelProvider) -> None:
    code = provider.code.lower()
    if code in ("anthropic", "nexbrain"):
        if model.model_name not in ANTHROPIC_EXECUTABLE_MODELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This model is not available for execution in the current phase. "
                    "Please select a supported model."
                ),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This model's provider is not supported for execution yet. "
                "Please select an Anthropic or Nexbrain model."
            ),
        )


def _get_usage_counter_or_402(db: Session, workspace_id: uuid.UUID) -> UsageCounter:
    now = datetime.now(timezone.utc)
    counter = db.scalar(
        select(UsageCounter)
        .where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.period_start <= now,
            UsageCounter.period_end >= now,
        )
        .order_by(UsageCounter.period_start.desc())
    )
    if counter is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "No active billing period found for this workspace. "
                "Please contact support or check your subscription."
            ),
        )
    return counter


def _validate_credits(
    counter: UsageCounter,
    credits_needed: int,
    plan_code: str,
    db: Session,
) -> None:
    plan = _get_plan_by_code(db, plan_code)
    monthly_limit = plan.monthly_ai_credits if plan else 0
    if counter.ai_credits_used + credits_needed > monthly_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient AI credits to run this agent.",
        )


def _increment_credits(db: Session, workspace_id: uuid.UUID, credits: int) -> None:
    """Atomic in-place increment — safe against concurrent requests."""
    now = datetime.now(timezone.utc)
    db.execute(
        update(UsageCounter)
        .where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.period_start <= now,
            UsageCounter.period_end >= now,
        )
        .values(ai_credits_used=UsageCounter.ai_credits_used + credits)
    )


def _log_run(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    model: AiModel,
    provider: AiModelProvider,
    status: str,
    error_message: str | None,
    credits_used: int,
    input_tokens: int | None,
    output_tokens: int | None,
    duration_ms: int | None,
) -> AgentTestRun:
    run = AgentTestRun(
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        ai_model_id=model.id,
        provider_code=provider.code,
        model_code=model.code,
        model_name=model.model_name,
        credits_used=credits_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message,
    )
    db.add(run)
    return run


# ── Plan helpers (local — avoids coupling to plan_service internals) ──────────

def _get_workspace_plan_code(db: Session, workspace_id: uuid.UUID) -> str:
    from app.enums import SubscriptionStatus

    sub = db.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id,
            WorkspaceSubscription.status == SubscriptionStatus.active.value,
        )
    )
    if sub is None:
        return "starter"
    plan = db.scalar(select(Plan).where(Plan.id == sub.plan_id))
    return plan.code if plan else "starter"


def _get_plan_by_code(db: Session, plan_code: str) -> Plan | None:
    return db.scalar(select(Plan).where(Plan.code == plan_code))
