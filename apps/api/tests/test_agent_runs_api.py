"""
API-level tests for /agent-runs (execucoes-log-prd.md). Filter/pagination
logic is covered directly against the service in test_agent_run_service.py
— these just confirm the HTTP layer (auth, serialization, 404, workspace
isolation) wires up correctly.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_tool_call import AgentToolCall
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_agent_run import ConversationAgentRun
from app.models.conversation_message import ConversationMessage
from app.models.workspace import Workspace


def _seed_run(db: Session, ws: Workspace, *, had_tool_error: bool = False) -> ConversationAgentRun:
    agent = Agent(workspace_id=ws.id, name="Bela", status="active")
    db.add(agent)
    db.flush()
    contact = Contact(workspace_id=ws.id, name="Luan Alves", phone="+5511999990000")
    db.add(contact)
    db.flush()
    conv = Conversation(
        workspace_id=ws.id,
        agent_id=agent.id,
        contact_id=contact.id,
        status="open",
        channel_type="internal",
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()
    msg = ConversationMessage(
        workspace_id=ws.id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content="Oi",
        content_type="text",
    )
    db.add(msg)
    db.flush()
    run = ConversationAgentRun(
        workspace_id=ws.id,
        conversation_id=conv.id,
        trigger_message_id=msg.id,
        agent_id=agent.id,
        status="success",
        had_tool_error=had_tool_error,
        credits_used=1,
    )
    db.add(run)
    db.flush()
    if had_tool_error:
        db.add(
            AgentToolCall(
                workspace_id=ws.id,
                conversation_agent_run_id=run.id,
                call_index=0,
                stop_reason="tool_use",
                input_tokens=10,
                output_tokens=5,
                duration_ms=100,
                tool_calls=[
                    {
                        "tool_name": "agendar_visita",
                        "tool_use_id": "t1",
                        "input": {},
                        "output": '{"status_code": 400}',
                        "status": "error",
                    }
                ],
            )
        )
    db.commit()
    return run


def test_list_agent_runs(client_a: TestClient, db: Session, workspace_a: Workspace):
    _seed_run(db, workspace_a, had_tool_error=True)
    r = client_a.get("/agent-runs")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["had_tool_error"] is True
    assert body[0]["contact_name"] == "Luan Alves"


def test_list_agent_runs_had_error_filter(
    client_a: TestClient, db: Session, workspace_a: Workspace
):
    _seed_run(db, workspace_a, had_tool_error=False)
    _seed_run(db, workspace_a, had_tool_error=True)
    r = client_a.get("/agent-runs", params={"had_error": True})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["had_tool_error"] is True


def test_get_agent_run_detail(client_a: TestClient, db: Session, workspace_a: Workspace):
    run = _seed_run(db, workspace_a, had_tool_error=True)
    r = client_a.get(f"/agent-runs/{run.id}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["tool_calls"]) == 1
    assert body["tool_calls"][0]["tool_name"] == "agendar_visita"
    assert body["tool_calls"][0]["status"] == "error"


def test_get_agent_run_404_for_unknown_id(client_a: TestClient):
    import uuid

    r = client_a.get(f"/agent-runs/{uuid.uuid4()}")
    assert r.status_code == 404


def test_agent_runs_isolated_by_workspace(
    client_b: TestClient, db: Session, workspace_a: Workspace
):
    _seed_run(db, workspace_a, had_tool_error=True)
    r = client_b.get("/agent-runs")
    assert r.status_code == 200
    assert r.json() == []


def test_agent_runs_requires_auth(unauthenticated_client: TestClient):
    r = unauthenticated_client.get("/agent-runs")
    assert r.status_code == 401
