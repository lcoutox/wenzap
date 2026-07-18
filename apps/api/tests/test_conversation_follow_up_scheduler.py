"""
Tests for the follow-up sweep (follow-up-tool-prd.md):
app/services/conversation_follow_up_scheduler.py's run_sweep_once /
_maybe_send_follow_up — eligibility, escalating steps, and the
claim-based (conversation_id, step_order, silence_anchor) concurrency guard.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.llm.schemas import LLMResponse
from app.models.agent import Agent
from app.models.agent_follow_up_settings import AgentFollowUpSettings
from app.models.agent_follow_up_step import AgentFollowUpStep
from app.models.agent_model_settings import AgentModelSettings
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_follow_up import ConversationFollowUp
from app.services.conversation_follow_up_scheduler import run_sweep_once

_NOW = datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc)


def _final_response(
    text="Oi, ainda por aí? Consigo te ajudar com mais alguma coisa?",
) -> LLMResponse:
    return LLMResponse(
        content=text,
        input_tokens=10,
        output_tokens=8,
        duration_ms=100,
        stop_reason="end_turn",
        content_blocks=[{"type": "text", "text": text}],
    )


def _make_model(db, workspace_id) -> AiModel:
    provider = AiModelProvider(id=uuid.uuid4(), code="anthropic", name="Anthropic", is_active=True)
    db.add(provider)
    db.flush()
    model = AiModel(
        id=uuid.uuid4(), provider_id=provider.id, code="claude-sonnet-4-6",
        display_name="Claude Sonnet", model_name="claude-sonnet-4-6",
        credits_per_message=1, min_plan_code="starter", is_default=True,
        is_active=True, sort_order=1,
    )
    db.add(model)
    db.commit()
    return model


def _make_agent(db, workspace_id, model: AiModel, *, status="active") -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Agente", status=status)
    db.add(agent)
    db.flush()
    db.add(AgentModelSettings(
        agent_id=agent.id, ai_model_id=model.id, model_name=model.model_name, temperature=0.7,
    ))
    db.commit()
    db.refresh(agent)
    return agent


def _make_conversation(
    db, workspace_id, agent_id, *, last_customer_message_at, ai_enabled=True,
    assigned_user_id=None, status="open", channel_type="whatsapp",
) -> Conversation:
    contact = Contact(workspace_id=workspace_id, name="Cliente", phone="+5511999999999")
    db.add(contact)
    db.flush()
    conv = Conversation(
        workspace_id=workspace_id, contact_id=contact.id, agent_id=agent_id,
        channel_type=channel_type, status=status, ai_enabled=ai_enabled,
        assigned_user_id=assigned_user_id, last_customer_message_at=last_customer_message_at,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def _enable_follow_up(db, workspace_id, agent_id, steps_hours: list[int], custom_instructions=None):
    db.add(AgentFollowUpSettings(
        workspace_id=workspace_id, agent_id=agent_id, is_enabled=True,
        custom_instructions=custom_instructions,
    ))
    for i, hours in enumerate(steps_hours):
        db.add(AgentFollowUpStep(
            workspace_id=workspace_id, agent_id=agent_id, step_order=i, delay_hours=hours,
        ))
    db.commit()


def test_sweep_sends_after_delay_elapsed(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    conv = _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=7)
    )

    with patch("app.llm.client.complete", return_value=_final_response()):
        sent = run_sweep_once(db)

    assert sent == 1
    followups = db.query(ConversationFollowUp).filter(
        ConversationFollowUp.conversation_id == conv.id
    ).all()
    assert len(followups) == 1
    assert followups[0].step_order == 0
    assert followups[0].conversation_message_id is not None


def test_sweep_skips_before_delay_elapsed(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=3)
    )

    with patch("app.llm.client.complete", return_value=_final_response()):
        sent = run_sweep_once(db)
    assert sent == 0


def test_sweep_skips_when_disabled(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=100)
    )
    # No AgentFollowUpSettings row at all — get-or-create only happens via the router.
    sent = run_sweep_once(db)
    assert sent == 0


def test_sweep_skips_without_scale_plan(db, workspace_a, subscription_a):
    """subscription_a defaults to starter — follow_up requires Scale+."""
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=100)
    )

    with patch("app.llm.client.complete", return_value=_final_response()):
        sent = run_sweep_once(db)
    assert sent == 0


def test_sweep_skips_when_human_assigned(db, workspace_a, scale_subscription_a, user_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=100),
        assigned_user_id=user_a.id,
    )
    sent = run_sweep_once(db)
    assert sent == 0


def test_sweep_skips_when_ai_disabled(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=100),
        ai_enabled=False,
    )
    sent = run_sweep_once(db)
    assert sent == 0


def test_sweep_skips_internal_channel(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=100),
        channel_type="internal",
    )
    sent = run_sweep_once(db)
    assert sent == 0


def test_sweep_sends_second_step_after_first(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6, 24])
    anchor = _NOW - timedelta(hours=30)
    conv = _make_conversation(db, workspace_a.id, agent.id, last_customer_message_at=anchor)

    with patch("app.llm.client.complete", return_value=_final_response()):
        first = run_sweep_once(db)
        second = run_sweep_once(db)

    assert first == 1  # step 0 (6h) fires
    assert second == 1  # step 1 (24h) fires in the very next pass (elapsed already 30h)
    steps_sent = sorted(
        f.step_order for f in
        db.query(ConversationFollowUp).filter(ConversationFollowUp.conversation_id == conv.id).all()
    )
    assert steps_sent == [0, 1]


def test_sweep_stops_after_all_steps_sent(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [1])
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=100)
    )

    with patch("app.llm.client.complete", return_value=_final_response()):
        first = run_sweep_once(db)
        second = run_sweep_once(db)  # same silence period — only 1 step configured

    assert first == 1
    assert second == 0


def test_sweep_resets_when_customer_replies(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    conv = _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=7)
    )

    with patch("app.llm.client.complete", return_value=_final_response()):
        first = run_sweep_once(db)
    assert first == 1

    # Customer replies — anchor moves forward, well within the 6h window again.
    conv.last_customer_message_at = _NOW - timedelta(hours=1)
    db.commit()

    with patch("app.llm.client.complete", return_value=_final_response()):
        second = run_sweep_once(db)
    assert second == 0  # too soon since the NEW anchor — old send doesn't count anymore


def test_sweep_skips_inactive_agent(db, workspace_a, scale_subscription_a):
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model, status="draft")
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    _make_conversation(
        db, workspace_a.id, agent.id, last_customer_message_at=_NOW - timedelta(hours=100)
    )

    with patch("app.llm.client.complete", return_value=_final_response()):
        sent = run_sweep_once(db)
    assert sent == 0


def test_claim_uniqueness_prevents_duplicate_send_for_same_period(
    db, workspace_a, scale_subscription_a
):
    """Simulates a race: a claim already exists for this exact
    (conversation, step, silence_anchor) — the sweep must not send again."""
    model = _make_model(db, workspace_a.id)
    agent = _make_agent(db, workspace_a.id, model)
    _enable_follow_up(db, workspace_a.id, agent.id, [6])
    anchor = _NOW - timedelta(hours=7)
    conv = _make_conversation(db, workspace_a.id, agent.id, last_customer_message_at=anchor)

    db.add(ConversationFollowUp(
        workspace_id=workspace_a.id, conversation_id=conv.id, agent_id=agent.id,
        step_order=0, silence_anchor=anchor, conversation_message_id=None, sent_at=_NOW,
    ))
    db.commit()

    with patch("app.llm.client.complete", return_value=_final_response()) as mock_complete:
        sent = run_sweep_once(db)

    assert sent == 0
    mock_complete.assert_not_called()
