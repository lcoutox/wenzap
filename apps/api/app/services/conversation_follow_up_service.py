"""
Follow-up content generation + delivery — follow-up-tool-prd.md.

Driven by conversation_follow_up_scheduler.py, not by a model-decided
tool_use call — there is no inbound trigger message, the backend itself
starts the turn after a period of customer silence. Reuses the same
system-prompt/history/credit/delivery machinery already proven in
conversation_agent_reply_service.py; only the final instruction (and the
lack of a fresh customer query to key RAG/catalog off of) differs.
"""

import logging
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.conversation import Conversation
from app.models.conversation_follow_up import ConversationFollowUp
from app.models.conversation_message import ConversationMessage
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.agent_context_builder import build_agent_instructions_block, build_system_prompt
from app.services.agent_llm_executor import run_agent_turn
from app.services.context_tier_service import calculate_credits
from app.services.conversation_context_builder import SENDER_LABELS

logger = logging.getLogger(__name__)

# Same executable-model allowlist as the Inbox reply path — a follow-up is
# just another automatic reply, only started by silence instead of a message.
ANTHROPIC_EXECUTABLE_MODELS: set[str] = {
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
}

_HISTORY_LIMIT = 20
_HISTORY_HEADER = "Recent conversation history:"
_FALLBACK_LABEL = "Mensagem"


def generate_and_send_follow_up(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    agent: Agent,
    step_number: int,
    total_steps: int,
    hours_silent: float,
    custom_instructions: str | None,
    claim: ConversationFollowUp,
) -> bool:
    """
    Generate follow-up text and send it.

    Returns True on success — response message, credit increment, and the
    claim's finalization (conversation_message_id/sent_at) are committed
    together as one transaction. Returns False on ANY failure (no model
    configured, insufficient credits, LLM error) WITHOUT committing — the
    caller must roll back so the claim row (inserted before this was called)
    doesn't linger and block the step from being retried on a later sweep.
    """
    model_settings = db.scalar(
        select(AgentModelSettings).where(AgentModelSettings.agent_id == agent.id)
    )
    if model_settings is None:
        return False
    model = db.scalar(select(AiModel).where(AiModel.id == model_settings.ai_model_id))
    if model is None or not model.is_active:
        return False
    provider = db.scalar(select(AiModelProvider).where(AiModelProvider.id == model.provider_id))
    if provider is None or not provider.is_active:
        return False
    if provider.code.lower() not in ("anthropic", "nexbrain") or \
            model.model_name not in ANTHROPIC_EXECUTABLE_MODELS:
        return False

    tier = getattr(model_settings, "context_window_tier", None) or "standard"
    credits_needed = calculate_credits(model.credits_per_message, tier)
    plan_code = _get_workspace_plan_code(db, workspace_id)
    counter = _get_usage_counter(db, workspace_id)
    if counter is None or not _has_credits(db, counter, credits_needed, plan_code):
        return False

    prompt_settings = _load_prompt_settings(db, agent)
    agent_instructions = build_agent_instructions_block(prompt_settings)
    system_prompt = build_system_prompt(
        agent_name=agent.name,
        agent_description=agent.description,
        system_prompt=prompt_settings.system_prompt or "",
        persona=prompt_settings.persona,
        response_style=getattr(prompt_settings, "response_style", None),
        language_mode=getattr(prompt_settings, "language_mode", None),
        agent_instructions_block=agent_instructions,
        has_tools=False,
    )

    history = _format_history(_fetch_recent_messages(db, conversation.id))
    instruction = _build_follow_up_instruction(
        hours_silent=hours_silent,
        step_number=step_number,
        total_steps=total_steps,
        custom_instructions=custom_instructions,
    )
    user_turn = f"{history}\n\n{instruction}" if history else instruction

    request = LLMRequest(
        model_name=model.model_name,
        system=system_prompt,
        messages=[LLMMessage(role="user", content=user_turn)],
        temperature=float(model_settings.temperature),
    )

    try:
        llm_response = run_agent_turn(request)
    except LLMProviderError:
        logger.exception(
            "follow_up_llm_error conversation_id=%s agent_id=%s step=%s",
            conversation.id, agent.id, step_number,
        )
        return False

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
    db.flush()  # assign id/created_at before it's referenced below

    conversation.last_message_at = response_msg.created_at or now
    conversation.updated_at = now
    _increment_credits(db, workspace_id, credits_needed)
    claim.conversation_message_id = response_msg.id
    claim.sent_at = now

    db.commit()
    db.refresh(response_msg)
    db.refresh(conversation)

    # Same channel gate as generate_conversation_agent_reply — web_widget
    # follow-ups are generated and saved into the thread either way (visible
    # next time the customer reopens the widget), just not actively pushed.
    if conversation.channel_type == "whatsapp":
        try:
            from app.services.messaging import deliver_outbound_message  # noqa: PLC0415
            deliver_outbound_message(db, response_msg, conversation)
        except Exception:
            logger.exception(
                "follow_up_delivery_failed conversation_id=%s message_id=%s",
                conversation.id, response_msg.id,
            )

    logger.info(
        "follow_up_sent conversation_id=%s agent_id=%s step=%s/%s",
        conversation.id, agent.id, step_number, total_steps,
    )
    return True


# ── Prompt construction helpers ─────────────────────────────────────────────────

def _build_follow_up_instruction(
    *, hours_silent: float, step_number: int, total_steps: int, custom_instructions: str | None
) -> str:
    hours = round(hours_silent)
    base = (
        f"O cliente está em silêncio há aproximadamente {hours} horas. Esta é a mensagem de "
        f"follow-up #{step_number} de {total_steps} da sequência de reengajamento configurada "
        "para este agente. Escreva uma mensagem curta, natural e não invasiva para tentar "
        "reengajar o cliente, sem soar como cobrança e sem se repetir do que já foi dito."
    )
    if custom_instructions:
        base += f"\n\nInstrução adicional do operador: {custom_instructions}"
    return base


def _fetch_recent_messages(db: Session, conversation_id: uuid.UUID) -> list[ConversationMessage]:
    rows = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(_HISTORY_LIMIT)
    ).all()
    return list(reversed(rows))


def _format_history(messages: list[ConversationMessage]) -> str:
    if not messages:
        return ""
    lines: list[str] = [_HISTORY_HEADER]
    for msg in messages:
        label = SENDER_LABELS.get((msg.direction, msg.sender_type), _FALLBACK_LABEL)
        content = (msg.content or "").strip()
        if content:
            lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _load_prompt_settings(db: Session, agent: Agent) -> AgentPromptSettings | SimpleNamespace:
    """Fallback for agents created before AgentPromptSettings existed as a
    satellite table. Uses a plain SimpleNamespace rather than
    AgentPromptSettings.__new__(...) + attribute assignment — that pattern
    (used elsewhere in this codebase, e.g. conversation_context_builder.py /
    agent_test_service.py) turns out to raise AttributeError: SQLAlchemy's
    InstrumentedAttribute.__set__ requires _sa_instance_state, which __new__
    never initializes (confirmed by reproducing it standalone). Out of scope
    to fix those other call sites here; this function just avoids the bug."""
    ps = db.scalar(select(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent.id))
    if ps is not None:
        return ps

    return SimpleNamespace(
        system_prompt=agent.system_prompt or "",
        persona=agent.persona,
        response_style=None,
        language_mode=None,
        knowledge_only=False,
        show_sources=False,
    )


# ── Plan/credits helpers (same shape as conversation_agent_reply_service.py) ────

def _get_workspace_plan_code(db: Session, workspace_id: uuid.UUID) -> str:
    from app.enums import SubscriptionStatus  # noqa: PLC0415

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
    from app.services.plan_service import get_or_create_usage_counter  # noqa: PLC0415
    try:
        return get_or_create_usage_counter(db, workspace_id)
    except Exception:
        return None


def _has_credits(db: Session, counter: UsageCounter, credits_needed: int, plan_code: str) -> bool:
    plan = db.scalar(select(Plan).where(Plan.code == plan_code))
    monthly_limit = plan.monthly_ai_credits if plan else 0
    return counter.ai_credits_used + credits_needed <= monthly_limit


def _increment_credits(db: Session, workspace_id: uuid.UUID, credits: int) -> None:
    from sqlalchemy import update  # noqa: PLC0415

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
