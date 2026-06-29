"""
Tests for WhatsApp AI.1 — outbound delivery of agent auto-replies.

Covers that conversation_agent_reply_service calls whatsapp_outbound_service
when conversation.channel_type == "whatsapp" after a successful LLM reply.

Uses the same unit-test approach as test_whatsapp_outbound_service:
SimpleNamespace objects, no real DB, httpx/LLM monkeypatched.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.conversation_agent_reply_service import generate_conversation_agent_reply

# ── Helpers ───────────────────────────────────────────────────────────────────


def _workspace_id() -> uuid.UUID:
    return uuid.uuid4()


def _conversation(channel_type: str = "whatsapp") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        assigned_user_id=None,
        ai_enabled=True,
        status="open",
        channel_type=channel_type,
        last_message_at=None,
        updated_at=None,
    )


def _trigger_message(conv: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=conv.workspace_id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content="Olá, preciso de ajuda.",
    )


def _agent(status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        name="TestAgent",
        status=status,
        system_prompt="Você é um assistente.",
        persona=None,
        description=None,
    )


def _model_settings(agent: SimpleNamespace, model_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(agent_id=agent.id, ai_model_id=model_id, temperature=0.7)


def _model(model_id: uuid.UUID, provider_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=model_id,
        provider_id=provider_id,
        model_name="claude-haiku-4-5",
        display_name="Claude Haiku",
        is_active=True,
        credits_per_message=1,
    )


def _provider(provider_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=provider_id, code="anthropic", name="Anthropic", is_active=True)


def _plan() -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), code="pro", monthly_ai_credits=10000)


def _counter() -> SimpleNamespace:
    return SimpleNamespace(workspace_id=uuid.uuid4(), ai_credits_used=0)


def _subscription() -> SimpleNamespace:
    return SimpleNamespace(workspace_id=uuid.uuid4(), plan_id=uuid.uuid4(), status="active")


def _make_db(agent, model_settings, model, provider, plan, counter, subscription) -> MagicMock:
    db = MagicMock()
    db.scalar.side_effect = [
        agent,           # Agent lookup
        model_settings,  # AgentModelSettings lookup
        model,           # AiModel lookup
        provider,        # AiModelProvider lookup
        subscription,    # WorkspaceSubscription lookup (in _get_workspace_plan_code)
        plan,            # Plan by id (in _get_workspace_plan_code)
        counter,         # UsageCounter (in _get_usage_counter)
        plan,            # Plan by code (in _has_credits)
    ]
    db.execute.return_value = None
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAgentOutboundDelivery:
    """Verify that agent replies on WhatsApp conversations trigger outbound delivery."""

    def test_whatsapp_conversation_triggers_outbound_delivery(self):
        """
        When generate_conversation_agent_reply succeeds and channel_type=whatsapp,
        deliver_human_message must be called with the response message.
        """
        conv = _conversation(channel_type="whatsapp")
        msg = _trigger_message(conv)
        agent = _agent()
        model_id = uuid.uuid4()
        provider_id = uuid.uuid4()
        model = _model(model_id, provider_id)
        provider = _provider(provider_id)
        ms = _model_settings(agent, model_id)
        sub = _subscription()
        plan = _plan()
        counter = _counter()

        db = _make_db(agent, ms, model, provider, plan, counter, sub)

        llm_response = SimpleNamespace(
            content="Olá! Posso ajudar.",
            input_tokens=10,
            output_tokens=5,
            duration_ms=200,
        )

        _pi = "app.services.conversation_agent_reply_service.detect_prompt_injection"
        _ctx = "app.services.conversation_agent_reply_service.build_conversation_context"
        _dl = "app.services.whatsapp_outbound_service.deliver_human_message"
        with patch("app.llm.client.complete", return_value=llm_response), \
             patch(_pi, return_value=False), \
             patch(_ctx) as mock_ctx, \
             patch(_dl) as mock_deliver:

            mock_ctx.return_value = SimpleNamespace(
                system_prompt="You are helpful.",
                conversation_history="",
                reply_instruction="Reply to: Olá",
                rag_used=False,
                retrieved_chunks_count=0,
                retrieval_duration_ms=None,
                retrieval_error_message=None,
                catalog_retrieval_attempted=False,
                catalog_items=[],
            )

            run = generate_conversation_agent_reply(
                db, conv.workspace_id, conv, msg  # type: ignore[arg-type]
            )

        assert run is not None
        assert run.status == "success"
        mock_deliver.assert_called_once()

    def test_non_whatsapp_conversation_does_not_trigger_outbound_delivery(self):
        """
        For channel_type='internal', deliver_human_message must NOT be called.
        """
        conv = _conversation(channel_type="internal")
        msg = _trigger_message(conv)
        agent = _agent()
        model_id = uuid.uuid4()
        provider_id = uuid.uuid4()
        model = _model(model_id, provider_id)
        provider = _provider(provider_id)
        ms = _model_settings(agent, model_id)
        sub = _subscription()
        plan = _plan()
        counter = _counter()

        db = _make_db(agent, ms, model, provider, plan, counter, sub)

        llm_response = SimpleNamespace(
            content="Olá! Posso ajudar.",
            input_tokens=10,
            output_tokens=5,
            duration_ms=200,
        )

        _pi = "app.services.conversation_agent_reply_service.detect_prompt_injection"
        _ctx = "app.services.conversation_agent_reply_service.build_conversation_context"
        _dl = "app.services.whatsapp_outbound_service.deliver_human_message"
        with patch("app.llm.client.complete", return_value=llm_response), \
             patch(_pi, return_value=False), \
             patch(_ctx) as mock_ctx, \
             patch(_dl) as mock_deliver:

            mock_ctx.return_value = SimpleNamespace(
                system_prompt="You are helpful.",
                conversation_history="",
                reply_instruction="Reply to: Olá",
                rag_used=False,
                retrieved_chunks_count=0,
                retrieval_duration_ms=None,
                retrieval_error_message=None,
                catalog_retrieval_attempted=False,
                catalog_items=[],
            )

            run = generate_conversation_agent_reply(
                db, conv.workspace_id, conv, msg  # type: ignore[arg-type]
            )

        assert run is not None
        assert run.status == "success"
        mock_deliver.assert_not_called()
