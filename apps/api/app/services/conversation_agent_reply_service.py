"""
Conversation Agent Reply Service — Phase 5.3.3.

Generates an automatic agent reply for a customer message received in the Inbox.

This service is called by the auto-trigger (Phase 5.3.4) after a customer
message is created. It is intentionally NOT connected to any endpoint or
ConversationMessageService yet — it runs in isolation in this phase.

Design decisions:
  - Returns ConversationAgentRun | None.
    None is returned when eligibility fails BEFORE we have enough context to
    create a run (no agent_id, trigger not from customer, etc.).
    A ConversationAgentRun is returned for every case where the agent is known.
  - Credits consumed ONLY on LLM success, atomically with the run insert.
  - The response ConversationMessage, credit increment, and run INSERT are all
    flushed in the same transaction, committed together for consistency.
  - Failures/skips/blocked produce a run with status != "success" and no
    response message, no credit consumption.
  - RAG retrieval failure degrades gracefully: LLM is still called without
    RAG context. The run records rag_used=False and the retrieval error message.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.llm import client as llm_client
from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.conversation import Conversation
from app.models.conversation_agent_run import ConversationAgentRun
from app.models.conversation_message import ConversationMessage
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.agent_guardrails import detect_prompt_injection
from app.services.conversation_context_builder import build_conversation_context

logger = logging.getLogger(__name__)

# Re-use the same executable model set as the Playground.
# Inbox replies use the same LLM infrastructure.
ANTHROPIC_EXECUTABLE_MODELS: set[str] = {
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
}

# ── Error codes ───────────────────────────────────────────────────────────────

EC_NOT_CUSTOMER_INBOUND = "not_customer_inbound"
EC_AI_DISABLED          = "ai_disabled"
EC_NO_AGENT             = "no_agent"
EC_STATUS_NOT_ALLOWED   = "status_not_allowed"
EC_HUMAN_ASSIGNED       = "human_assigned"
EC_AGENT_NOT_FOUND      = "agent_not_found"
EC_AGENT_INACTIVE       = "agent_inactive"
EC_NO_MODEL             = "no_model"
EC_NO_CREDITS           = "no_credits"
EC_PROMPT_INJECTION     = "prompt_injection"
EC_LLM_ERROR            = "llm_error"
EC_CONTEXT_ERROR        = "context_error"
EC_UNKNOWN_ERROR        = "unknown_error"

_ALLOWED_CONV_STATUSES = {"open", "pending"}


def generate_conversation_agent_reply(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    trigger_message: ConversationMessage,
) -> ConversationAgentRun | None:
    """
    Attempt to generate an automatic agent reply for *trigger_message*.

    Returns
    -------
    ConversationAgentRun
        Always returned when the agent is known (active or inactive, model
        found or not, LLM succeeded or failed).
    None
        Returned when eligibility fails before we can identify a valid agent:
        - trigger message is not inbound/customer
        - conversation.ai_enabled is False
        - conversation.agent_id is None
        - conversation.status is resolved/archived
        - conversation.assigned_user_id is set (human has taken over)
        - agent record not found / FK gone (can't reference in run)
    """
    # ── 1. Trigger message must be inbound/customer ───────────────────────────
    if trigger_message.direction != "inbound" or trigger_message.sender_type != "customer":
        return None  # not_customer_inbound — no run, no noise

    # ── 2. Conversation eligibility ───────────────────────────────────────────
    if not conversation.ai_enabled:
        logger.info(
            "agent_reply_skip reason=ai_disabled conversation_id=%s", conversation.id
        )
        return None
    if conversation.agent_id is None:
        logger.info(
            "agent_reply_skip reason=no_agent conversation_id=%s", conversation.id
        )
        return None
    if conversation.status not in _ALLOWED_CONV_STATUSES:
        logger.info(
            "agent_reply_skip reason=status_%s conversation_id=%s",
            conversation.status, conversation.id,
        )
        return None
    if conversation.assigned_user_id is not None:
        logger.info(
            "agent_reply_skip reason=human_assigned conversation_id=%s assigned_user_id=%s",
            conversation.id, conversation.assigned_user_id,
        )
        return None

    # ── 3. Load agent (workspace-scoped) ─────────────────────────────────────
    agent = db.scalar(
        select(Agent).where(
            Agent.id == conversation.agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if agent is None:
        logger.info(
            "agent_reply_skip reason=agent_not_found conversation_id=%s agent_id=%s",
            conversation.id, conversation.agent_id,
        )
        return None

    if agent.status != "active":
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=None,
            status="skipped",
            error_code=EC_AGENT_INACTIVE,
        )

    # ── 4. Load model settings ────────────────────────────────────────────────
    model_settings = db.scalar(
        select(AgentModelSettings).where(AgentModelSettings.agent_id == agent.id)
    )
    if model_settings is None:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=None,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message="Agent has no model configured.",
        )

    model = db.scalar(select(AiModel).where(AiModel.id == model_settings.ai_model_id))
    if model is None or not model.is_active:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message="Configured model not found or inactive.",
        )

    provider = db.scalar(
        select(AiModelProvider).where(AiModelProvider.id == model.provider_id)
    )
    if provider is None or not provider.is_active:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message="Model provider not found or inactive.",
        )

    # Only Anthropic/Nexbrain models are executable in this phase.
    if provider.code.lower() not in ("anthropic", "nexbrain") or \
            model.model_name not in ANTHROPIC_EXECUTABLE_MODELS:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message=(
                f"Model '{model.model_name}' is not supported for automatic replies."
            ),
        )

    # ── 5. Credit check ───────────────────────────────────────────────────────
    credits_needed = model.credits_per_message
    plan_code = _get_workspace_plan_code(db, workspace_id)
    counter = _get_usage_counter(db, workspace_id)
    if counter is None or not _has_credits(db, counter, credits_needed, plan_code):
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_CREDITS,
            error_message="Insufficient AI credits.",
        )

    # ── 6. Prompt injection guard ─────────────────────────────────────────────
    if detect_prompt_injection(trigger_message.content):
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="blocked",
            error_code=EC_PROMPT_INJECTION,
            error_message="Trigger message blocked by guardrails.",
        )

    # ── 7. Build conversation context ─────────────────────────────────────────
    try:
        ctx = build_conversation_context(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            agent=agent,
            trigger_message=trigger_message,
        )
    except Exception as exc:  # noqa: BLE001
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_CONTEXT_ERROR,
            error_message=f"Context build error: {str(exc)[:400]}",
        )

    # ── 8. Call LLM ───────────────────────────────────────────────────────────
    # Build the user turn: history block + reply instruction, so the model
    # sees the full conversation before the latest customer message.
    user_turn = (
        f"{ctx.conversation_history}\n\n{ctx.reply_instruction}"
        if ctx.conversation_history
        else ctx.reply_instruction
    )

    request = LLMRequest(
        model_name=model.model_name,
        system=ctx.system_prompt,
        messages=[LLMMessage(role="user", content=user_turn)],
        temperature=float(model_settings.temperature),
    )

    try:
        llm_response = llm_client.complete(request)
    except LLMProviderError as exc:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_LLM_ERROR,
            error_message=str(exc.message)[:500],
            rag_used=ctx.rag_used,
            retrieved_chunks_count=ctx.retrieved_chunks_count,
            retrieval_duration_ms=ctx.retrieval_duration_ms,
        )

    # ── 9. Persist response message ───────────────────────────────────────────
    now = datetime.now(timezone.utc)
    response_msg = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_type="agent",
        agent_id=agent.id,
        content=llm_response.content,
        content_type="text",
    )
    db.add(response_msg)
    db.flush()  # Assign id and created_at.

    # Update conversation timestamps.
    conversation.last_message_at = response_msg.created_at or now
    conversation.updated_at = now

    # ── 10. Consume credits (atomic) ──────────────────────────────────────────
    _increment_credits(db, workspace_id, credits_needed)

    # ── 11. Persist success run ───────────────────────────────────────────────
    run = ConversationAgentRun(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        trigger_message_id=trigger_message.id,
        response_message_id=response_msg.id,
        agent_id=agent.id,
        ai_model_id=model.id,
        status="success",
        credits_used=credits_needed,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
        duration_ms=llm_response.duration_ms,
        rag_used=ctx.rag_used,
        retrieved_chunks_count=ctx.retrieved_chunks_count,
        retrieval_duration_ms=ctx.retrieval_duration_ms,
        # Surface retrieval errors in error_message even on success so they
        # are visible in logs without marking the run as failed.
        error_message=ctx.retrieval_error_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    logger.info(
        "agent_reply_success conversation_id=%s run_id=%s response_message_id=%s",
        conversation.id, run.id, response_msg.id,
    )

    # Deliver agent reply to WhatsApp when the conversation came from that channel.
    if conversation.channel_type == "whatsapp":
        try:
            from app.services.whatsapp_outbound_service import (  # noqa: PLC0415
                deliver_human_message,
            )
            deliver_human_message(db, response_msg, conversation)
        except Exception:
            import logging as _logging  # noqa: PLC0415
            _logging.getLogger(__name__).exception(
                "whatsapp_outbound agent delivery failed conversation=%s message=%s",
                conversation.id,
                response_msg.id,
            )

    return run


# ── Internal helpers ──────────────────────────────────────────────────────────

def _save_run(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    trigger_message: ConversationMessage,
    agent: Agent,
    model: AiModel | None,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    rag_used: bool = False,
    retrieved_chunks_count: int = 0,
    retrieval_duration_ms: int | None = None,
) -> ConversationAgentRun:
    """Persist a non-success run and commit."""
    logger.info(
        "agent_reply_run status=%s error_code=%s conversation_id=%s error=%s",
        status, error_code, conversation.id, error_message,
    )
    run = ConversationAgentRun(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        trigger_message_id=trigger_message.id,
        response_message_id=None,
        agent_id=agent.id,
        ai_model_id=model.id if model is not None else None,
        status=status,
        credits_used=0,
        rag_used=rag_used,
        retrieved_chunks_count=retrieved_chunks_count,
        retrieval_duration_ms=retrieval_duration_ms,
        error_code=error_code,
        error_message=error_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


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


def _get_usage_counter(db: Session, workspace_id: uuid.UUID) -> UsageCounter | None:
    now = datetime.now(timezone.utc)
    return db.scalar(
        select(UsageCounter)
        .where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.period_start <= now,
            UsageCounter.period_end >= now,
        )
        .order_by(UsageCounter.period_start.desc())
    )


def _has_credits(
    db: Session,
    counter: UsageCounter,
    credits_needed: int,
    plan_code: str,
) -> bool:
    plan = db.scalar(select(Plan).where(Plan.code == plan_code))
    monthly_limit = plan.monthly_ai_credits if plan else 0
    return counter.ai_credits_used + credits_needed <= monthly_limit


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
