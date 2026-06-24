"""
Tests for Phase 5.3.1 — ConversationAgentRun model and migration.

Covers:
- Minimal run creation (success)
- Default values (credits_used, rag_used, retrieved_chunks_count)
- Failed run with error_code and error_message
- Run with token/duration fields
- Run with response_message_id
- Status check constraint (invalid status raises)
- FK CASCADE: deleting conversation removes runs
- FK CASCADE: deleting trigger_message removes runs
- FK SET NULL: deleting response_message sets response_message_id to null
- FK SET NULL: deleting ai_model sets ai_model_id to null
- workspace_id required
- VALID_CONVERSATION_AGENT_RUN_STATUSES constant
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.ai_model import AiModel
from app.models.conversation import Conversation
from app.models.conversation_agent_run import (
    VALID_CONVERSATION_AGENT_RUN_STATUSES,
    ConversationAgentRun,
)
from app.models.conversation_message import ConversationMessage
from app.models.workspace import Workspace

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_agent(db: Session, workspace: Workspace) -> Agent:
    agent = Agent(workspace_id=workspace.id, name="Test Agent", status="active")
    db.add(agent)
    db.flush()
    db.refresh(agent)
    return agent


def _make_conversation(db: Session, workspace: Workspace, agent: Agent) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        agent_id=agent.id,
        status="open",
        channel_type="internal",
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


def _make_message(
    db: Session,
    workspace: Workspace,
    conversation: Conversation,
    direction: str = "inbound",
    sender_type: str = "customer",
    content: str = "Hello",
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        direction=direction,
        sender_type=sender_type,
        content=content,
    )
    db.add(msg)
    db.flush()
    db.refresh(msg)
    return msg


def _make_run(
    db: Session,
    workspace: Workspace,
    conversation: Conversation,
    trigger_message: ConversationMessage,
    agent: Agent,
    **kwargs,
) -> ConversationAgentRun:
    run = ConversationAgentRun(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        trigger_message_id=trigger_message.id,
        agent_id=agent.id,
        status=kwargs.pop("status", "success"),
        **kwargs,
    )
    db.add(run)
    db.flush()
    db.refresh(run)
    return run


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_run_minimal_success(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(db, workspace_a, conv, trigger, agent)
    db.commit()
    db.refresh(run)

    assert run.id is not None
    assert run.workspace_id == workspace_a.id
    assert run.conversation_id == conv.id
    assert run.trigger_message_id == trigger.id
    assert run.agent_id == agent.id
    assert run.status == "success"
    assert run.created_at is not None


def test_run_defaults(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(db, workspace_a, conv, trigger, agent)
    db.commit()
    db.refresh(run)

    assert run.credits_used == 0
    assert run.rag_used is False
    assert run.retrieved_chunks_count == 0
    assert run.input_tokens is None
    assert run.output_tokens is None
    assert run.duration_ms is None
    assert run.retrieval_duration_ms is None
    assert run.response_message_id is None
    assert run.ai_model_id is None
    assert run.error_code is None
    assert run.error_message is None


def test_run_failed_with_error_info(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(
        db,
        workspace_a,
        conv,
        trigger,
        agent,
        status="failed",
        error_code="no_credits",
        error_message="Workspace has insufficient credits.",
    )
    db.commit()
    db.refresh(run)

    assert run.status == "failed"
    assert run.error_code == "no_credits"
    assert run.error_message == "Workspace has insufficient credits."
    assert run.credits_used == 0


def test_run_blocked_status(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(
        db, workspace_a, conv, trigger, agent,
        status="blocked",
        error_code="prompt_injection",
        error_message="Message blocked by guardrails.",
    )
    db.commit()
    db.refresh(run)

    assert run.status == "blocked"


def test_run_skipped_status(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(db, workspace_a, conv, trigger, agent, status="skipped")
    db.commit()
    db.refresh(run)

    assert run.status == "skipped"


def test_run_with_tokens_and_duration(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(
        db, workspace_a, conv, trigger, agent,
        credits_used=2,
        input_tokens=150,
        output_tokens=80,
        duration_ms=1234,
    )
    db.commit()
    db.refresh(run)

    assert run.credits_used == 2
    assert run.input_tokens == 150
    assert run.output_tokens == 80
    assert run.duration_ms == 1234


def test_run_with_rag_metadata(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(
        db, workspace_a, conv, trigger, agent,
        rag_used=True,
        retrieved_chunks_count=3,
        retrieval_duration_ms=210,
    )
    db.commit()
    db.refresh(run)

    assert run.rag_used is True
    assert run.retrieved_chunks_count == 3
    assert run.retrieval_duration_ms == 210


def test_run_with_response_message(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)
    response = _make_message(
        db, workspace_a, conv,
        direction="outbound",
        sender_type="agent",
        content="Olá! Como posso ajudar?",
    )

    run = _make_run(
        db, workspace_a, conv, trigger, agent,
        response_message_id=response.id,
    )
    db.commit()
    db.refresh(run)

    assert run.response_message_id == response.id


def test_run_with_ai_model(db: Session, workspace_a: Workspace, ai_model: AiModel):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(
        db, workspace_a, conv, trigger, agent,
        ai_model_id=ai_model.id,
    )
    db.commit()
    db.refresh(run)

    assert run.ai_model_id == ai_model.id


def test_run_invalid_status_raises(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    with pytest.raises(Exception):
        db.add(ConversationAgentRun(
            workspace_id=workspace_a.id,
            conversation_id=conv.id,
            trigger_message_id=trigger.id,
            agent_id=agent.id,
            status="running",  # invalid
        ))
        db.flush()
        db.execute(text("SELECT 1"))


def test_run_workspace_id_required(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    with pytest.raises(Exception):
        db.add(ConversationAgentRun(
            conversation_id=conv.id,
            trigger_message_id=trigger.id,
            agent_id=agent.id,
            status="success",
        ))
        db.flush()


def test_cascade_delete_conversation_removes_run(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(db, workspace_a, conv, trigger, agent)
    run_id = run.id
    db.commit()

    db.delete(conv)
    db.commit()

    remaining = db.query(ConversationAgentRun).filter_by(id=run_id).first()
    assert remaining is None


def test_cascade_delete_trigger_message_removes_run(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(db, workspace_a, conv, trigger, agent)
    run_id = run.id
    db.commit()

    db.delete(trigger)
    db.commit()

    remaining = db.query(ConversationAgentRun).filter_by(id=run_id).first()
    assert remaining is None


def test_set_null_response_message_on_delete(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)
    response = _make_message(
        db, workspace_a, conv,
        direction="outbound",
        sender_type="agent",
        content="Resposta do agente.",
    )

    run = _make_run(
        db, workspace_a, conv, trigger, agent,
        response_message_id=response.id,
    )
    run_id = run.id
    db.commit()

    db.delete(response)
    db.commit()

    db.expire_all()
    run = db.query(ConversationAgentRun).filter_by(id=run_id).first()
    assert run is not None
    assert run.response_message_id is None


def test_set_null_ai_model_on_delete(db: Session, workspace_a: Workspace, ai_model: AiModel):
    agent = _make_agent(db, workspace_a)
    conv = _make_conversation(db, workspace_a, agent)
    trigger = _make_message(db, workspace_a, conv)

    run = _make_run(
        db, workspace_a, conv, trigger, agent,
        ai_model_id=ai_model.id,
    )
    run_id = run.id
    db.commit()

    db.delete(ai_model)
    db.commit()

    db.expire_all()
    run = db.query(ConversationAgentRun).filter_by(id=run_id).first()
    assert run is not None
    assert run.ai_model_id is None


# ── Constants ─────────────────────────────────────────────────────────────────


def test_valid_statuses_constant():
    assert "success" in VALID_CONVERSATION_AGENT_RUN_STATUSES
    assert "failed" in VALID_CONVERSATION_AGENT_RUN_STATUSES
    assert "skipped" in VALID_CONVERSATION_AGENT_RUN_STATUSES
    assert "blocked" in VALID_CONVERSATION_AGENT_RUN_STATUSES
    assert len(VALID_CONVERSATION_AGENT_RUN_STATUSES) == 4
