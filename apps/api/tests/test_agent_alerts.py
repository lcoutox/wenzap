"""
Tests for agent_alert_service.py and routers/agent_alerts.py.

No test coverage existed for this system before whatsapp-official-only-prd.md
(confirmed: zero test files referencing agent_alerts). Covers the pre-existing
notify_agent_error() plus the new notify_channel_disabled() (workspace/
channel-level alert, conversation_id=None) and the router's handling of a
null conversation_id (previously would have serialized as the string "None").
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_alert import AgentAlert
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.services.agent_alert_service import notify_agent_error, notify_channel_disabled
from tests.conftest import _make_client, _make_user, _make_workspace


def _make_agent(db: Session, ws_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=ws_id, name="Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_conversation(db: Session, ws_id: uuid.UUID, agent: Agent) -> Conversation:
    contact = Contact(workspace_id=ws_id, name="Cliente")
    db.add(contact)
    db.flush()
    conv = Conversation(
        workspace_id=ws_id, agent_id=agent.id, contact_id=contact.id,
        channel_type="internal", status="open",
    )
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


class TestNotifyAgentError:
    def test_creates_alert_with_conversation_id(self, db: Session, workspace_a):
        agent = _make_agent(db, workspace_a.id)
        conv = _make_conversation(db, workspace_a.id, agent)

        notify_agent_error(
            db,
            workspace_id=workspace_a.id,
            agent_id=agent.id,
            conversation_id=conv.id,
            error_code="llm_error",
            error_message="Anthropic 500",
        )

        alert = db.scalar(
            select(AgentAlert).where(AgentAlert.agent_id == agent.id)
        )
        assert alert is not None
        assert alert.conversation_id == conv.id
        assert alert.error_code == "llm_error"
        assert alert.error_message_admin == "Anthropic 500"
        assert "temporariamente indisponível" in alert.error_message_user
        assert alert.is_read is False


class TestNotifyChannelDisabled:
    def test_creates_alert_without_conversation_id(self, db: Session, workspace_a):
        agent = _make_agent(db, workspace_a.id)

        notify_channel_disabled(
            db,
            workspace_id=workspace_a.id,
            agent_id=agent.id,
            error_code="whatsapp_channel_disconnected",
            error_message_user="Reconecte via Integração oficial da Meta.",
            error_message_admin="Evolution auto_reply disabled during official-only migration",
        )

        alert = db.scalar(
            select(AgentAlert).where(AgentAlert.agent_id == agent.id)
        )
        assert alert is not None
        assert alert.conversation_id is None
        assert alert.error_code == "whatsapp_channel_disconnected"
        assert alert.error_message_user == "Reconecte via Integração oficial da Meta."
        assert alert.is_read is False

    def test_never_raises_on_db_error(self, db: Session):
        """workspace_id/agent_id that don't exist violate the FK — must be
        swallowed, not propagate, matching notify_agent_error's contract."""
        notify_channel_disabled(
            db,
            workspace_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            error_code="whatsapp_channel_disconnected",
            error_message_user="x",
            error_message_admin="x",
        )
        # No exception raised — that's the assertion.


class TestListAgentAlertsRoute:
    def test_alert_without_conversation_serializes_null(
        self, db: Session, user_a, workspace_a
    ):
        agent = _make_agent(db, workspace_a.id)
        notify_channel_disabled(
            db,
            workspace_id=workspace_a.id,
            agent_id=agent.id,
            error_code="whatsapp_channel_disconnected",
            error_message_user="Reconecte via Meta.",
            error_message_admin="admin detail",
        )

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.get("/agent-alerts", params={"is_read": False})

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["conversation_id"] is None
        assert body[0]["error_message_user"] == "Reconecte via Meta."

    def test_alert_with_conversation_serializes_string(
        self, db: Session, user_a, workspace_a
    ):
        agent = _make_agent(db, workspace_a.id)
        conv = _make_conversation(db, workspace_a.id, agent)
        notify_agent_error(
            db,
            workspace_id=workspace_a.id,
            agent_id=agent.id,
            conversation_id=conv.id,
            error_code="llm_error",
            error_message="boom",
        )

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.get("/agent-alerts", params={"is_read": False})

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["conversation_id"] == str(conv.id)

    def test_workspace_isolation(self, db: Session, user_a, workspace_a):
        other_owner = _make_user(db, f"u{uuid.uuid4().hex[:6]}@t.com", "Other")
        workspace_b = _make_workspace(db, other_owner, f"ws-{uuid.uuid4().hex[:6]}", "WS B")
        other_agent = _make_agent(db, workspace_b.id)
        notify_channel_disabled(
            db,
            workspace_id=workspace_b.id,
            agent_id=other_agent.id,
            error_code="whatsapp_channel_disconnected",
            error_message_user="não deveria aparecer",
            error_message_admin="x",
        )

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.get("/agent-alerts", params={"is_read": False})

        assert resp.status_code == 200
        assert resp.json() == []
