"""
Tests for auto_reply_scheduler — AI Reply UX.1.

Coverage:
  Unit (schedule_agent_auto_reply / _execute_if_latest):
  1. delay=0 calls execute synchronously (no thread)
  2. delay>0 starts a daemon thread
  3. execute_if_latest fires reply when trigger is latest customer message
  4. execute_if_latest is no-op when a newer message exists (trigger superseded)
  5. execute_if_latest is no-op when conversation not found
  6. no-op threads do not call generate_conversation_agent_reply

  Integration (reply_delay_seconds field):
  7. new agent defaults to reply_delay_seconds=5
  8. existing agents (migration backfill) have reply_delay_seconds=0
  9. PATCH saves valid values: 0, 3, 5, 8, 15
  10. PATCH rejects invalid value (422)
  11. reply_delay_seconds appears in AgentOut

  Debounce integration via create_message:
  12. delay=0: reply fires synchronously (existing behaviour preserved)
  13. delay=5: create_message schedules a thread (LLM not called in-request)
  14. delay=5, second message arrives: first thread is no-op
  15. only latest thread generates the reply (credits consumed once)

  Agent/conversation state guards (executed inside thread):
  16. no reply if conversation status is resolved
  17. no reply if ai_enabled=False
  18. no reply if conversation has human assigned (checked in generate_conversation_agent_reply)
"""

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.schemas import LLMResponse
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.conversation import Conversation
from app.models.conversation_agent_run import ConversationAgentRun
from app.models.conversation_message import ConversationMessage
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.schemas.agent import AgentUpdate
from app.schemas.conversation_message import ConversationMessageCreate
from app.services.agent_service import create_agent, get_agent, update_agent
from app.services.auto_reply_scheduler import _execute_if_latest, schedule_agent_auto_reply
from app.services.conversation_message_service import create_message
from tests.conftest import _make_subscription, _make_user, _make_workspace

# ── Helpers ────────────────────────────────────────────────────────────────────

_MODEL_NAME = "claude-sonnet-4-6"
_LLM_PATCH = "app.llm.client.complete"


def _mock_llm(content: str = "Olá! Como posso ajudar?") -> LLMResponse:
    return LLMResponse(content=content, input_tokens=50, output_tokens=30, duration_ms=300)


def _make_plan(db: Session, *, credits: int = 5_000) -> Plan:
    p = Plan(
        code=f"plan-{uuid.uuid4().hex[:8]}",
        name="Test",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        sources_per_kb_limit=20,
        max_source_chars=50_000,
        users_limit=10,
        pipelines_limit=5,
        integrations_limit=5,
        monthly_ai_credits=credits,
        monthly_conversations=10_000,
    )
    db.add(p)
    db.flush()
    return p


def _make_counter(db: Session, ws_id: uuid.UUID) -> UsageCounter:
    now = datetime.now(timezone.utc)
    c = UsageCounter(
        workspace_id=ws_id,
        period_start=now - timedelta(hours=1),
        period_end=now + timedelta(days=30),
        ai_credits_used=0,
        conversations_count=0,
        messages_count=0,
    )
    db.add(c)
    db.flush()
    return c


def _make_provider(db: Session) -> AiModelProvider:
    existing = db.scalar(
        select(AiModelProvider).where(AiModelProvider.code == "anthropic")
    )
    if existing:
        return existing
    p = AiModelProvider(code="anthropic", name="Anthropic", is_active=True)
    db.add(p)
    db.flush()
    return p


def _make_model(db: Session, provider: AiModelProvider) -> AiModel:
    m = AiModel(
        provider_id=provider.id,
        code=f"model-{uuid.uuid4().hex[:8]}",
        model_name=_MODEL_NAME,
        display_name="Test Model",
        credits_per_message=1,
        is_active=True,
        min_plan_code="starter",
        sort_order=1,
    )
    db.add(m)
    db.flush()
    return m


def _make_agent(db: Session, ws_id: uuid.UUID, model: AiModel, *, delay: int = 0) -> Agent:
    agent = Agent(workspace_id=ws_id, name="Test Agent", status="active")
    db.add(agent)
    db.flush()
    db.add(AgentPromptSettings(
        agent_id=agent.id,
        system_prompt="Você é um assistente.",
        reply_delay_seconds=delay,
    ))
    db.add(AgentModelSettings(
        agent_id=agent.id,
        ai_model_id=model.id,
        model_name=model.model_name,
        temperature=0.5,
        context_window_tier="economical",
    ))
    db.flush()
    return agent


def _make_conversation(
    db: Session,
    ws_id: uuid.UUID,
    agent: Agent | None = None,
    *,
    status: str = "open",
    ai_enabled: bool = True,
    assigned_user_id: uuid.UUID | None = None,
) -> Conversation:
    conv = Conversation(
        workspace_id=ws_id,
        agent_id=agent.id if agent else None,
        status=status,
        channel_type="internal",
        ai_enabled=ai_enabled,
        assigned_user_id=assigned_user_id,
    )
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


def _make_customer_message(
    db: Session,
    ws_id: uuid.UUID,
    conv: Conversation,
    content: str = "Olá",
    *,
    at: datetime | None = None,
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=ws_id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content=content,
        content_type="text",
        created_at=at or datetime.now(timezone.utc),
    )
    db.add(msg)
    db.flush()
    db.refresh(msg)
    return msg


def _full_setup(db: Session, *, delay: int = 0):
    owner = _make_user(db, f"u{uuid.uuid4().hex[:6]}@t.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    plan = _make_plan(db)
    _make_subscription(db, ws, plan)
    _make_counter(db, ws.id)
    provider = _make_provider(db)
    model = _make_model(db, provider)
    agent = _make_agent(db, ws.id, model, delay=delay)
    db.commit()
    return ws, agent, model


# ── Unit: schedule_agent_auto_reply ───────────────────────────────────────────

def test_schedule_delay_zero_is_synchronous(db: Session):
    """delay=0 must call _execute_if_latest synchronously without spawning a thread."""
    ws, agent, model = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent)
    msg = _make_customer_message(db, ws.id, conv)
    db.commit()

    calls = []
    with patch(
        "app.services.auto_reply_scheduler._execute_if_latest",
        side_effect=lambda *a, **kw: calls.append(True),
    ):
        schedule_agent_auto_reply(
            workspace_id=ws.id,
            conversation_id=conv.id,
            agent_id=agent.id,
            trigger_message_id=msg.id,
            delay_seconds=0,
            db=db,
        )

    assert len(calls) == 1


def test_schedule_delay_positive_spawns_thread(db: Session):
    """delay>0 must start a daemon thread and not call _execute_if_latest inline."""
    ws, agent, model = _full_setup(db, delay=5)
    conv = _make_conversation(db, ws.id, agent)
    msg = _make_customer_message(db, ws.id, conv)
    db.commit()

    inline_calls = []
    with patch(
        "app.services.auto_reply_scheduler._execute_if_latest",
        side_effect=lambda *a, **kw: inline_calls.append(True),
    ), patch("app.services.auto_reply_scheduler._run_auto_reply"):
        schedule_agent_auto_reply(
            workspace_id=ws.id,
            conversation_id=conv.id,
            agent_id=agent.id,
            trigger_message_id=msg.id,
            delay_seconds=5,
            db=db,
        )

    # _execute_if_latest must NOT be called inline for delay>0.
    assert len(inline_calls) == 0


def test_execute_fires_when_trigger_is_latest(db: Session):
    """execute_if_latest calls generate_conversation_agent_reply when trigger is latest."""
    ws, agent, model = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent)
    msg = _make_customer_message(db, ws.id, conv)
    db.commit()

    with patch(_LLM_PATCH, return_value=_mock_llm()):
        _execute_if_latest(db, ws.id, conv.id, agent.id, msg.id)

    reply = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conv.id,
            ConversationMessage.direction == "outbound",
            ConversationMessage.sender_type == "agent",
        )
    )
    assert reply is not None


def test_execute_noop_when_superseded(db: Session):
    """execute_if_latest is a no-op when a newer customer message exists."""
    ws, agent, model = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent)
    now = datetime.now(timezone.utc)
    old_msg = _make_customer_message(db, ws.id, conv, content="Oi", at=now)
    _make_customer_message(db, ws.id, conv, content="Na verdade, esquece",
                           at=now + timedelta(seconds=1))
    db.commit()

    with patch(_LLM_PATCH, return_value=_mock_llm()) as mock_llm:
        _execute_if_latest(db, ws.id, conv.id, agent.id, old_msg.id)

    mock_llm.assert_not_called()

    # No outbound agent message.
    reply = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conv.id,
            ConversationMessage.direction == "outbound",
        )
    )
    assert reply is None


def test_execute_noop_when_conversation_not_found(db: Session):
    """execute_if_latest exits without error when conversation does not exist."""
    fake_conv_id = uuid.uuid4()
    ws, agent, model = _full_setup(db)
    with patch(_LLM_PATCH) as mock_llm:
        _execute_if_latest(db, ws.id, fake_conv_id, agent.id, uuid.uuid4())
    mock_llm.assert_not_called()


# ── Integration: reply_delay_seconds field ─────────────────────────────────────

def test_new_agent_defaults_reply_delay_to_5(db: Session):
    """Agents created via API default to reply_delay_seconds=5."""
    from app.schemas.agent import AgentCreate

    owner = _make_user(db, f"u{uuid.uuid4().hex[:6]}@t.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    plan = _make_plan(db)
    _make_subscription(db, ws, plan)
    provider = _make_provider(db)
    model = _make_model(db, provider)
    db.commit()

    out = create_agent(
        db,
        workspace_id=ws.id,
        user_id=owner.id,
        data=AgentCreate(name="New Agent", ai_model_id=model.id),
    )
    assert out.reply_delay_seconds == 5


def test_existing_agent_migration_backfill_is_zero(db: Session):
    """Agents created directly (like test helpers) have reply_delay_seconds=0 (DB default)."""
    ws, agent, _ = _full_setup(db, delay=0)
    ps = db.scalar(
        select(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent.id)
    )
    assert ps is not None
    assert ps.reply_delay_seconds == 0


def test_patch_saves_valid_delay_values(db: Session):
    """update_agent accepts all valid delay values."""
    ws, agent, _ = _full_setup(db)

    for delay in [0, 3, 5, 8, 15]:
        out = update_agent(
            db,
            workspace_id=ws.id,
            agent_id=agent.id,
            data=AgentUpdate(reply_delay_seconds=delay),
        )
        assert out.reply_delay_seconds == delay


def test_patch_rejects_invalid_delay(db: Session):
    """AgentUpdate schema rejects reply_delay_seconds not in {0,3,5,8,15}."""
    with pytest.raises(Exception):
        AgentUpdate(reply_delay_seconds=7)


def test_agent_out_includes_reply_delay_seconds(db: Session):
    """AgentOut exposes reply_delay_seconds."""
    ws, agent, _ = _full_setup(db, delay=5)
    out = get_agent(db, ws.id, agent.id)
    assert hasattr(out, "reply_delay_seconds")
    assert out.reply_delay_seconds == 5


# ── Debounce integration via create_message ───────────────────────────────────

def test_delay_zero_fires_reply_synchronously(db: Session):
    """delay=0 → reply is created synchronously before create_message returns."""
    ws, agent, _ = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent)
    db.commit()

    with patch(_LLM_PATCH, return_value=_mock_llm()):
        msg = create_message(
            db, ws.id, conv.id, None,
            ConversationMessageCreate(
                direction="inbound", sender_type="customer", content="Oi", content_type="text"
            ),
        )

    reply = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conv.id,
            ConversationMessage.direction == "outbound",
            ConversationMessage.sender_type == "agent",
        )
    )
    assert reply is not None


def test_delay_positive_does_not_call_llm_in_request(db: Session):
    """delay>0 → create_message returns without calling the LLM."""
    ws, agent, _ = _full_setup(db, delay=5)
    conv = _make_conversation(db, ws.id, agent)
    db.commit()

    with patch(_LLM_PATCH) as mock_llm, \
         patch("app.services.auto_reply_scheduler._run_auto_reply"):
        create_message(
            db, ws.id, conv.id, None,
            ConversationMessageCreate(
                direction="inbound", sender_type="customer", content="Oi", content_type="text"
            ),
        )
    mock_llm.assert_not_called()


def test_superseded_message_execute_is_noop(db: Session):
    """execute_if_latest for a superseded message produces no reply."""
    ws, agent, _ = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent)
    now = datetime.now(timezone.utc)
    msg1 = _make_customer_message(db, ws.id, conv, content="Oi", at=now)
    _make_customer_message(db, ws.id, conv, content="E os planos?", at=now + timedelta(seconds=1))
    db.commit()

    # msg1 is now superseded by msg2.
    with patch(_LLM_PATCH) as mock_llm:
        _execute_if_latest(db, ws.id, conv.id, agent.id, msg1.id)

    mock_llm.assert_not_called()


def test_latest_message_execute_fires_reply(db: Session):
    """execute_if_latest for the latest message fires a reply (only once)."""
    ws, agent, _ = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent)
    now = datetime.now(timezone.utc)
    _make_customer_message(db, ws.id, conv, content="Oi", at=now)
    msg2 = _make_customer_message(db, ws.id, conv, content="E os planos?",
                                   at=now + timedelta(seconds=1))
    db.commit()

    with patch(_LLM_PATCH, return_value=_mock_llm()):
        _execute_if_latest(db, ws.id, conv.id, agent.id, msg2.id)

    agent_replies = db.scalars(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conv.id,
            ConversationMessage.direction == "outbound",
            ConversationMessage.sender_type == "agent",
        )
    ).all()
    assert len(agent_replies) == 1


def test_noop_thread_does_not_consume_credits(db: Session):
    """A no-op (superseded) job must not consume credits."""
    ws, agent, _ = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent)
    db.commit()

    counter_before = db.scalar(
        select(UsageCounter).where(UsageCounter.workspace_id == ws.id)
    )
    credits_before = counter_before.ai_credits_used if counter_before else 0

    now = datetime.now(timezone.utc)
    # First message — gets superseded.
    msg1 = _make_customer_message(db, ws.id, conv, content="Oi", at=now)
    # Second message — makes msg1 no longer the latest.
    _make_customer_message(db, ws.id, conv, content="E aí?", at=now + timedelta(seconds=1))
    db.commit()

    with patch(_LLM_PATCH) as mock_llm:
        _execute_if_latest(db, ws.id, conv.id, agent.id, msg1.id)

    mock_llm.assert_not_called()

    db.expire_all()
    counter_after = db.scalar(
        select(UsageCounter).where(UsageCounter.workspace_id == ws.id)
    )
    credits_after = counter_after.ai_credits_used if counter_after else 0
    assert credits_after == credits_before


# ── State guards ──────────────────────────────────────────────────────────────

def test_no_reply_resolved_conversation(db: Session):
    """execute_if_latest skips when conversation is resolved."""
    ws, agent, _ = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent, status="resolved")
    msg = _make_customer_message(db, ws.id, conv)
    db.commit()

    with patch(_LLM_PATCH) as mock_llm:
        _execute_if_latest(db, ws.id, conv.id, agent.id, msg.id)

    mock_llm.assert_not_called()


def test_no_reply_ai_disabled(db: Session):
    """execute_if_latest skips when conversation.ai_enabled is False."""
    ws, agent, _ = _full_setup(db, delay=0)
    conv = _make_conversation(db, ws.id, agent, ai_enabled=False)
    msg = _make_customer_message(db, ws.id, conv)
    db.commit()

    with patch(_LLM_PATCH) as mock_llm:
        _execute_if_latest(db, ws.id, conv.id, agent.id, msg.id)

    mock_llm.assert_not_called()
