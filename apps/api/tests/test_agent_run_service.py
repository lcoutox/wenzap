"""
Tests for the Agent Run service (execucoes-log-prd.md) — the read-only
layer backing the "Execuções" dashboard screen and the Inbox error
indicator. Builds ConversationAgentRun/AgentToolCall rows directly (no LLM
calls) since this module only reads what conversation_agent_reply_service
and agent_llm_executor already write.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_tool_call import AgentToolCall
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_agent_run import ConversationAgentRun
from app.models.conversation_message import ConversationMessage
from app.services.agent_run_service import get_agent_run_detail, list_agent_runs
from tests.conftest import _make_user, _make_workspace


def _make_agent(db: Session, ws_id: uuid.UUID, name: str = "Bela") -> Agent:
    agent = Agent(workspace_id=ws_id, name=name, status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_contact(db: Session, ws_id: uuid.UUID, name: str = "Luan Alves") -> Contact:
    contact = Contact(workspace_id=ws_id, name=name, phone="+5511999990000")
    db.add(contact)
    db.flush()
    return contact


def _make_conversation(
    db: Session, ws_id: uuid.UUID, agent: Agent, contact: Contact
) -> Conversation:
    conv = Conversation(
        workspace_id=ws_id,
        agent_id=agent.id,
        contact_id=contact.id,
        status="open",
        channel_type="internal",
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()
    return conv


def _make_message(db: Session, ws_id: uuid.UUID, conv: Conversation) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=ws_id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content="Oi",
        content_type="text",
    )
    db.add(msg)
    db.flush()
    return msg


def _make_run(
    db: Session,
    ws_id: uuid.UUID,
    conv: Conversation,
    agent: Agent,
    msg: ConversationMessage,
    *,
    status: str = "success",
    had_tool_error: bool = False,
    created_at=None,
) -> ConversationAgentRun:
    run = ConversationAgentRun(
        workspace_id=ws_id,
        conversation_id=conv.id,
        trigger_message_id=msg.id,
        agent_id=agent.id,
        status=status,
        had_tool_error=had_tool_error,
        credits_used=1,
    )
    if created_at is not None:
        run.created_at = created_at
    db.add(run)
    db.flush()
    return run


def _make_tool_call(
    db: Session,
    ws_id: uuid.UUID,
    run: ConversationAgentRun,
    tool_calls: list[dict],
    *,
    call_index: int = 0,
) -> AgentToolCall:
    call = AgentToolCall(
        workspace_id=ws_id,
        conversation_agent_run_id=run.id,
        call_index=call_index,
        stop_reason="tool_use",
        input_tokens=10,
        output_tokens=5,
        duration_ms=100,
        tool_calls=tool_calls,
    )
    db.add(call)
    db.flush()
    return call


class TestListAgentRuns:
    def test_returns_runs_newest_first_with_contact_and_agent_names(self, db: Session):
        owner = _make_user(db, f"ar1-{uuid.uuid4().hex[:6]}@test.com", "AR1")
        ws = _make_workspace(db, owner, f"ar-ws-{uuid.uuid4().hex[:6]}", "AR WS")
        agent = _make_agent(db, ws.id)
        contact = _make_contact(db, ws.id)
        conv = _make_conversation(db, ws.id, agent, contact)
        msg1 = _make_message(db, ws.id, conv)
        msg2 = _make_message(db, ws.id, conv)
        # Explicit timestamps — created_at ties within the same millisecond
        # would otherwise make "newest first" ordering flaky.
        now = datetime.now(timezone.utc)
        _make_run(db, ws.id, conv, agent, msg1, created_at=now)
        run2 = _make_run(db, ws.id, conv, agent, msg2, created_at=now + timedelta(seconds=1))
        db.commit()

        runs = list_agent_runs(db, ws.id)
        assert len(runs) == 2
        assert runs[0]["id"] == str(run2.id)  # newest first
        assert runs[0]["contact_name"] == "Luan Alves"
        assert runs[0]["agent_name"] == "Bela"

    def test_does_not_return_other_workspace_runs(self, db: Session):
        owner_a = _make_user(db, f"ar2a-{uuid.uuid4().hex[:6]}@test.com", "AR2A")
        ws_a = _make_workspace(db, owner_a, f"ar-wsa-{uuid.uuid4().hex[:6]}", "AR A")
        owner_b = _make_user(db, f"ar2b-{uuid.uuid4().hex[:6]}@test.com", "AR2B")
        ws_b = _make_workspace(db, owner_b, f"ar-wsb-{uuid.uuid4().hex[:6]}", "AR B")

        agent_a = _make_agent(db, ws_a.id)
        contact_a = _make_contact(db, ws_a.id)
        conv_a = _make_conversation(db, ws_a.id, agent_a, contact_a)
        msg_a = _make_message(db, ws_a.id, conv_a)
        _make_run(db, ws_a.id, conv_a, agent_a, msg_a)
        db.commit()

        assert list_agent_runs(db, ws_b.id) == []

    def test_had_error_filter_includes_failed_status_and_tool_error(self, db: Session):
        owner = _make_user(db, f"ar3-{uuid.uuid4().hex[:6]}@test.com", "AR3")
        ws = _make_workspace(db, owner, f"ar-ws-{uuid.uuid4().hex[:6]}", "AR WS")
        agent = _make_agent(db, ws.id)
        contact = _make_contact(db, ws.id)
        conv = _make_conversation(db, ws.id, agent, contact)

        msg_ok = _make_message(db, ws.id, conv)
        _make_run(db, ws.id, conv, agent, msg_ok, status="success", had_tool_error=False)

        msg_tool_fail = _make_message(db, ws.id, conv)
        _make_run(db, ws.id, conv, agent, msg_tool_fail, status="success", had_tool_error=True)

        msg_crash = _make_message(db, ws.id, conv)
        _make_run(db, ws.id, conv, agent, msg_crash, status="failed", had_tool_error=False)
        db.commit()

        runs = list_agent_runs(db, ws.id, had_error=True)
        assert len(runs) == 2
        statuses = {(r["status"], r["had_tool_error"]) for r in runs}
        assert ("success", True) in statuses
        assert ("failed", False) in statuses

    def test_filters_by_agent_id(self, db: Session):
        owner = _make_user(db, f"ar4-{uuid.uuid4().hex[:6]}@test.com", "AR4")
        ws = _make_workspace(db, owner, f"ar-ws-{uuid.uuid4().hex[:6]}", "AR WS")
        agent_1 = _make_agent(db, ws.id, name="Agent 1")
        agent_2 = _make_agent(db, ws.id, name="Agent 2")
        contact = _make_contact(db, ws.id)
        conv_1 = _make_conversation(db, ws.id, agent_1, contact)
        conv_2 = _make_conversation(db, ws.id, agent_2, contact)
        msg_1 = _make_message(db, ws.id, conv_1)
        msg_2 = _make_message(db, ws.id, conv_2)
        _make_run(db, ws.id, conv_1, agent_1, msg_1)
        _make_run(db, ws.id, conv_2, agent_2, msg_2)
        db.commit()

        runs = list_agent_runs(db, ws.id, agent_id=agent_1.id)
        assert len(runs) == 1
        assert runs[0]["agent_name"] == "Agent 1"

    def test_filters_by_tool_name(self, db: Session):
        owner = _make_user(db, f"ar5-{uuid.uuid4().hex[:6]}@test.com", "AR5")
        ws = _make_workspace(db, owner, f"ar-ws-{uuid.uuid4().hex[:6]}", "AR WS")
        agent = _make_agent(db, ws.id)
        contact = _make_contact(db, ws.id)
        conv = _make_conversation(db, ws.id, agent, contact)

        msg_cal = _make_message(db, ws.id, conv)
        run_cal = _make_run(db, ws.id, conv, agent, msg_cal)
        _make_tool_call(
            db,
            ws.id,
            run_cal,
            [
                {
                    "tool_name": "agendar_visita",
                    "tool_use_id": "t1",
                    "input": {},
                    "output": "ok",
                    "status": "success",
                },
            ],
        )

        msg_other = _make_message(db, ws.id, conv)
        run_other = _make_run(db, ws.id, conv, agent, msg_other)
        _make_tool_call(
            db,
            ws.id,
            run_other,
            [
                {
                    "tool_name": "mover_card_pipeline",
                    "tool_use_id": "t2",
                    "input": {},
                    "output": "ok",
                    "status": "success",
                },
            ],
        )
        db.commit()

        runs = list_agent_runs(db, ws.id, tool_name="agendar_visita")
        assert len(runs) == 1
        assert runs[0]["id"] == str(run_cal.id)

    def test_tool_names_deduplicated_and_populated(self, db: Session):
        owner = _make_user(db, f"ar6-{uuid.uuid4().hex[:6]}@test.com", "AR6")
        ws = _make_workspace(db, owner, f"ar-ws-{uuid.uuid4().hex[:6]}", "AR WS")
        agent = _make_agent(db, ws.id)
        contact = _make_contact(db, ws.id)
        conv = _make_conversation(db, ws.id, agent, contact)
        msg = _make_message(db, ws.id, conv)
        run = _make_run(db, ws.id, conv, agent, msg)
        _make_tool_call(
            db,
            ws.id,
            run,
            [
                {
                    "tool_name": "verificar_horarios_calcom",
                    "tool_use_id": "t1",
                    "input": {},
                    "output": "ok",
                    "status": "success",
                },
            ],
            call_index=0,
        )
        _make_tool_call(
            db,
            ws.id,
            run,
            [
                {
                    "tool_name": "verificar_horarios_calcom",
                    "tool_use_id": "t2",
                    "input": {},
                    "output": "ok",
                    "status": "success",
                },
            ],
            call_index=1,
        )
        db.commit()

        runs = list_agent_runs(db, ws.id)
        assert runs[0]["tool_names"] == ["verificar_horarios_calcom"]


class TestGetAgentRunDetail:
    def test_returns_flattened_tool_calls(self, db: Session):
        owner = _make_user(db, f"ar7-{uuid.uuid4().hex[:6]}@test.com", "AR7")
        ws = _make_workspace(db, owner, f"ar-ws-{uuid.uuid4().hex[:6]}", "AR WS")
        agent = _make_agent(db, ws.id)
        contact = _make_contact(db, ws.id)
        conv = _make_conversation(db, ws.id, agent, contact)
        msg = _make_message(db, ws.id, conv)
        run = _make_run(db, ws.id, conv, agent, msg, had_tool_error=True)
        _make_tool_call(
            db,
            ws.id,
            run,
            [
                {
                    "tool_name": "agendar_visita",
                    "tool_use_id": "t1",
                    "input": {"name": "Luan"},
                    "output": '{"status_code": 400}',
                    "status": "error",
                },
            ],
        )
        db.commit()

        detail = get_agent_run_detail(db, ws.id, run.id)
        assert detail is not None
        assert detail["had_tool_error"] is True
        assert len(detail["tool_calls"]) == 1
        assert detail["tool_calls"][0]["tool_name"] == "agendar_visita"
        assert detail["tool_calls"][0]["status"] == "error"
        assert detail["tool_calls"][0]["input"] == {"name": "Luan"}

    def test_returns_none_for_missing_run(self, db: Session):
        owner = _make_user(db, f"ar8-{uuid.uuid4().hex[:6]}@test.com", "AR8")
        ws = _make_workspace(db, owner, f"ar-ws-{uuid.uuid4().hex[:6]}", "AR WS")
        assert get_agent_run_detail(db, ws.id, uuid.uuid4()) is None

    def test_returns_none_for_run_in_other_workspace(self, db: Session):
        owner_a = _make_user(db, f"ar9a-{uuid.uuid4().hex[:6]}@test.com", "AR9A")
        ws_a = _make_workspace(db, owner_a, f"ar-wsa-{uuid.uuid4().hex[:6]}", "AR A")
        owner_b = _make_user(db, f"ar9b-{uuid.uuid4().hex[:6]}@test.com", "AR9B")
        ws_b = _make_workspace(db, owner_b, f"ar-wsb-{uuid.uuid4().hex[:6]}", "AR B")

        agent = _make_agent(db, ws_a.id)
        contact = _make_contact(db, ws_a.id)
        conv = _make_conversation(db, ws_a.id, agent, contact)
        msg = _make_message(db, ws_a.id, conv)
        run = _make_run(db, ws_a.id, conv, agent, msg)
        db.commit()

        assert get_agent_run_detail(db, ws_b.id, run.id) is None
