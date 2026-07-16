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

RAG policy (Phase 4.3):
  If the agent has active Knowledge Base connections, chunks are retrieved
  AFTER prompt injection detection of the user's message. A blocked message
  never triggers retrieval, embedding, or LLM calls.

  RAG failures (embedding error, provider down) degrade gracefully: the LLM
  is still called without RAG context; the error is recorded in agent_test_runs.

  Chunks that contain prompt injection patterns are excluded from the prompt
  (recorded in agent_test_run_retrieved_chunks with injected_into_prompt=False).

  Context is capped at settings.rag_max_context_chars; chunks are dropped by
  rank (lowest similarity first) — never cut mid-text.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.llm import client as llm_client
from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.agent_test_run import AgentTestRun
from app.models.agent_test_run_retrieved_chunk import AgentTestRunRetrievedChunk
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.agent_test import AgentTestModelInfo, AgentTestRequest, AgentTestResponse
from app.services import playground_service
from app.services.agent_catalog_scope_service import get_allowed_category_ids
from app.services.agent_context_builder import (
    build_agent_instructions_block,
    build_rag_context_block,
    build_system_prompt,
)
from app.services.agent_guardrails import detect_prompt_injection, get_safe_refusal_message
from app.services.ai_model_service import PLAN_TIER
from app.services.catalog_retrieval_service import retrieve_catalog_context
from app.services.context_tier_service import calculate_credits, get_tier_config
from app.services.knowledge_retrieval_service import RetrievedChunk, retrieve_context_for_agent

logger = logging.getLogger(__name__)

# Executable models: Anthropic Claude + OpenAI GPT + Nexbrain wrappers
# provider=anthropic and provider=nexbrain: Claude models
# provider=openai: GPT models
EXECUTABLE_MODELS: set[str] = {
    # Anthropic Claude
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    # OpenAI GPT
    "gpt-4o-mini",
    "gpt-4o",
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
    tier = getattr(model_settings, "context_window_tier", None) or "standard"
    credits_needed = calculate_credits(model.credits_per_message, tier)
    counter = _get_usage_counter_or_402(db, workspace_id)
    _validate_credits(counter, credits_needed, plan_code, db)

    # Validate prompt settings early so a missing prompt never causes a session
    # to be created. The actual build_system_prompt() call is deferred until
    # after RAG retrieval so the rag_context can be included.
    prompt_settings = _get_prompt_settings(db, agent)

    # ── Resolve or create session (all validations passed) ────────────────────
    if data.session_id is not None:
        session = playground_service.get_session_or_404(
            db, workspace_id, agent_id, data.session_id
        )
    else:
        session = playground_service.create_session_pending(
            db, workspace_id, agent_id, user_id
        )
        db.flush()

    # ── Persist user message & update session metadata ────────────────────────
    playground_service.save_user_message(db, session.id, data.message)
    playground_service.update_session_title_from_first_message(db, session, data.message)
    playground_service.touch_session(db, session)
    db.flush()

    # ── Prompt injection detection ────────────────────────────────────────────
    # Checked after session + user message are flushed so the attempt is visible
    # in Playground history. No retrieval, no LLM call, no credits consumed.
    if detect_prompt_injection(data.message):
        refusal = get_safe_refusal_message()
        playground_service.save_assistant_message(
            db, session.id, refusal, agent_test_run_id=None
        )
        playground_service.touch_session(db, session)
        db.commit()
        return AgentTestResponse(
            reply=refusal,
            credits_used=0,
            input_tokens=0,
            output_tokens=0,
            duration_ms=0,
            model=AgentTestModelInfo(
                display_name=model.display_name,
                provider=provider.code,
                model_name=model.model_name,
            ),
            session_id=session.id,
            rag_used=False,
            retrieved_chunks_count=0,
        )

    # ── RAG retrieval ─────────────────────────────────────────────────────────
    # Runs only when the user message is clean. Provider=None means the service
    # reads from settings (MockEmbeddingProvider in dev/test, OpenAI in prod).
    retrieval_result = retrieve_context_for_agent(
        db,
        workspace_id=workspace_id,
        agent_id=agent_id,
        query=data.message,
    )

    # Filter chunks that contain prompt injection patterns before injecting into prompt.
    chunks_safe = _filter_chunks_injection(retrieval_result.chunks)

    # Apply context size limit from agent's context tier (falls back to global config).
    tier_cfg = get_tier_config(tier)
    rag_max_chars = tier_cfg.get("rag_max_chars", app_settings.rag_max_context_chars)
    chunks_final = _truncate_chunks_to_limit(chunks_safe, rag_max_chars)

    chunk_contents = [c.content for c in chunks_final]
    rag_context = build_rag_context_block(chunk_contents) if chunks_final else None

    # Python object IDs of chunks that enter the prompt (for audit logging).
    # Using id() instead of chunk_id supports chunks with chunk_id=None (e.g. in tests).
    injected_obj_ids: set[int] = {id(c) for c in chunks_final}

    # Pre-compute RAG summary fields for _log_run.
    rag_used_flag = len(chunks_final) > 0
    injected_count = len(chunks_final)
    retrieved_count_for_run = injected_count if retrieval_result.retrieval_attempted else None
    score_max = max(c.score for c in chunks_final) if chunks_final else None
    score_min = min(c.score for c in chunks_final) if chunks_final else None

    # ── Catalog retrieval (Catálogo.3 / Catálogo.5 / Agent Tools.2) ─────────
    if agent.catalog_enabled:
        allowed_category_ids = get_allowed_category_ids(
            db, agent_id=agent_id, workspace_id=workspace_id
        )
        catalog_result = retrieve_catalog_context(
            db,
            workspace_id=workspace_id,
            query=data.message,
            limit=tier_cfg.get("catalog_limit", 3),
            allowed_category_ids=allowed_category_ids,
        )
    else:
        from app.services.catalog_retrieval_service import CatalogRetrievalResult  # noqa: PLC0415
        catalog_result = CatalogRetrievalResult(retrieval_attempted=False)

    # ── Build system prompt (deferred until after retrieval) ──────────────────
    ps_response_style = getattr(prompt_settings, "response_style", None)
    ps_language_mode = getattr(prompt_settings, "language_mode", None)
    ps_knowledge_only = getattr(prompt_settings, "knowledge_only", False)
    ps_show_sources = getattr(prompt_settings, "show_sources", False)

    agent_instructions = build_agent_instructions_block(prompt_settings)

    system = build_system_prompt(
        agent_name=agent.name,
        agent_description=agent.description,
        system_prompt=prompt_settings.system_prompt or "",
        persona=prompt_settings.persona,
        response_style=ps_response_style,
        language_mode=ps_language_mode,
        knowledge_only=ps_knowledge_only,
        show_sources=ps_show_sources,
        knowledge_fallback=getattr(prompt_settings, "knowledge_fallback", None),
        rag_context=rag_context,
        catalog_context=catalog_result.context_block,
        agent_instructions_block=agent_instructions,
    )

    if app_settings.ai_prompt_debug:
        _log_playground_prompt_debug(
            agent_id=agent.id,
            user_id=user_id,
            has_custom_instructions=bool(prompt_settings.system_prompt),
            has_tone=bool(getattr(prompt_settings, "persona", None)),
            response_style=ps_response_style,
            has_knowledge_context=bool(rag_context),
            has_catalog_context=bool(catalog_result.context_block),
            system_prompt=system,
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
        # Error path — user message + run error committed together, no credits.
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
            rag_used=rag_used_flag,
            retrieval_attempted=retrieval_result.retrieval_attempted,
            retrieved_chunks_count=retrieved_count_for_run,
            retrieval_duration_ms=retrieval_result.retrieval_duration_ms,
            retrieval_score_max=score_max,
            retrieval_score_min=score_min,
            retrieval_error_message=retrieval_result.error_message,
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
        rag_used=rag_used_flag,
        retrieval_attempted=retrieval_result.retrieval_attempted,
        retrieved_chunks_count=retrieved_count_for_run,
        retrieval_duration_ms=retrieval_result.retrieval_duration_ms,
        retrieval_score_max=score_max,
        retrieval_score_min=score_min,
        retrieval_error_message=retrieval_result.error_message,
    )
    db.flush()  # get run.id before using it as FK

    # Persist all retrieved chunks (injected and filtered) for audit.
    if retrieval_result.chunks:
        _persist_retrieved_chunks(db, run.id, retrieval_result.chunks, injected_obj_ids)

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
        rag_used=rag_used_flag,
        retrieved_chunks_count=injected_count,
        catalog_retrieval_attempted=catalog_result.retrieval_attempted,
        catalog_items_count=len(catalog_result.items),
        catalog_items_used=[
            {
                "id": str(i.id),
                "name": i.name,
                "score": i.score,
                "semantic_score": i.semantic_score,
                "lexical_score": i.lexical_score,
                "retrieval_method": i.retrieval_method,
            }
            for i in catalog_result.items
        ],
        catalog_retrieval_method=(
            catalog_result.items[0].retrieval_method if catalog_result.items else None
        ),
    )


# ── RAG helpers ───────────────────────────────────────────────────────────────

def _filter_chunks_injection(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Return only chunks whose content does not trigger injection detection."""
    return [c for c in chunks if not detect_prompt_injection(c.content)]


def _truncate_chunks_to_limit(
    chunks: list[RetrievedChunk],
    max_chars: int,
) -> list[RetrievedChunk]:
    """
    Return a prefix of *chunks* whose total character count fits within *max_chars*.

    Rules:
    - Chunks are already ordered by rank (highest similarity first).
    - A single chunk that exceeds max_chars by itself is skipped.
    - Iteration stops as soon as adding the next chunk would overflow.
    """
    result: list[RetrievedChunk] = []
    total = 0
    for chunk in chunks:
        chunk_len = len(chunk.content)
        if chunk_len > max_chars:
            continue  # single chunk too big — skip, not break
        if total + chunk_len > max_chars:
            break
        result.append(chunk)
        total += chunk_len
    return result


def _persist_retrieved_chunks(
    db: Session,
    run_id: uuid.UUID,
    retrieved_chunks: list[RetrievedChunk],
    injected_obj_ids: set[int],
) -> None:
    """
    Persist audit rows for every chunk that was a candidate in this retrieval.

    injected_obj_ids contains Python id() of chunks that entered the LLM prompt.
    Using object identity (not chunk_id) correctly handles chunks with chunk_id=None.
    """
    for chunk in retrieved_chunks:
        db.add(AgentTestRunRetrievedChunk(
            agent_test_run_id=run_id,
            knowledge_chunk_id=chunk.chunk_id,
            knowledge_base_id=chunk.knowledge_base_id,
            source_id=chunk.source_id,
            score=chunk.score,
            rank=chunk.rank,
            injected_into_prompt=id(chunk) in injected_obj_ids,
        ))


# ── Internal helpers ──────────────────────────────────────────────────────────

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

    if ps is not None:
        # For guided mode with non-empty guided_config, no system_prompt required.
        mode = getattr(ps, "instructions_mode", None) or "guided"
        if mode == "advanced":
            adv = (getattr(ps, "advanced_prompt", None) or "").strip()
            effective = adv or system_prompt.strip()
            if not effective:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configure advanced_prompt before testing this agent.",
                )
        elif mode == "guided":
            cfg = getattr(ps, "guided_config", None) or {}
            has_guided = bool(
                cfg and any(
                    v for v in cfg.values()
                    if v is not None and v != [] and v != ""
                )
            )
            if not has_guided and not system_prompt.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configure agent instructions before testing.",
                )
        return ps

    # Legacy stub (no prompt settings row)
    effective_prompt = system_prompt.strip()
    if not effective_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A system_prompt is required to test this agent.",
        )

    stub = AgentPromptSettings.__new__(AgentPromptSettings)
    stub.system_prompt = system_prompt
    stub.persona = persona
    stub.response_style = None   # defaults to "balanced" in builder
    stub.language_mode = None    # defaults to "auto" in builder
    stub.knowledge_only = False
    stub.show_sources = False
    stub.instructions_mode = "guided"
    stub.guided_config = None
    stub.advanced_prompt = None
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
    if code in ("anthropic", "nexbrain", "openai"):
        if model.model_name not in EXECUTABLE_MODELS:
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
                "Please select a model from Anthropic, OpenAI, or Nexbrain."
            ),
        )


def _get_usage_counter_or_402(db: Session, workspace_id: uuid.UUID) -> UsageCounter:
    from app.services.plan_service import get_or_create_usage_counter  # noqa: PLC0415
    return get_or_create_usage_counter(db, workspace_id)


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
    # RAG metadata (Phase 4.3) — all defaulted so callers don't need to know about RAG.
    rag_used: bool = False,
    retrieval_attempted: bool = False,
    retrieved_chunks_count: int | None = None,
    retrieval_duration_ms: int | None = None,
    retrieval_score_max: float | None = None,
    retrieval_score_min: float | None = None,
    retrieval_error_message: str | None = None,
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
        rag_used=rag_used,
        retrieval_attempted=retrieval_attempted,
        retrieved_chunks_count=retrieved_chunks_count,
        retrieval_duration_ms=retrieval_duration_ms,
        retrieval_score_max=retrieval_score_max,
        retrieval_score_min=retrieval_score_min,
        retrieval_error_message=retrieval_error_message,
    )
    db.add(run)
    return run


# ── Debug helpers ─────────────────────────────────────────────────────────────

def _log_playground_prompt_debug(
    *,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
    has_custom_instructions: bool,
    has_tone: bool,
    response_style: str | None,
    has_knowledge_context: bool,
    has_catalog_context: bool,
    system_prompt: str,
) -> None:
    sections: list[str] = ["identity"]
    if has_custom_instructions:
        sections.append("operator_instructions")
    if has_tone:
        sections.append("persona")
    if response_style:
        sections.append(f"response_style:{response_style}")
    if has_knowledge_context:
        sections.append("rag")
    if has_catalog_context:
        sections.append("catalog")
    sections.append("safety_rules")

    logger.info(
        "AI_PROMPT_DEBUG[playground] agent_id=%s user_id=%s "
        "sections=%s system_prompt_length=%d "
        "has_custom_instructions=%s has_tone=%s response_style=%s "
        "has_knowledge_context=%s has_catalog_context=%s",
        agent_id,
        user_id,
        ",".join(sections),
        len(system_prompt),
        has_custom_instructions,
        has_tone,
        response_style,
        has_knowledge_context,
        has_catalog_context,
    )

    is_dev = not app_settings.auth_cookie_secure
    if is_dev:
        preview = system_prompt[:2000]
        logger.info("AI_PROMPT_DEBUG[playground] system_prompt_preview:\n%s", preview)


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
