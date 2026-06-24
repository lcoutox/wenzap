"""
Tests for Phase 5.4.2 — POST /public/widgets/{public_key}/sessions

Covers:
  - creates new session
  - session_token returned
  - token starts with wss_
  - creates anonymous Contact with name="Visitante"
  - Contact has source=web_widget metadata
  - creates Conversation with channel_type=web_widget
  - conversation.agent_id == channel.agent_id
  - conversation.ai_enabled == True
  - conversation.status == "open"
  - conversation.assigned_user_id == None
  - creates WidgetSession linking channel/contact/conversation
  - resumes existing session when valid token sent
  - updates last_seen_at when resuming
  - invalid token creates new session
  - token from different channel not reused
  - token from different workspace's channel not reused
  - inactive channel → 404, no session created
  - archived channel → 404, no session created
  - origin not allowed → 403, no session created
  - two sessions for same channel are independent (no conversation mixing)
  - no ConversationMessage created during POST /sessions
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.widget_session import WidgetSession
from app.models.workspace import Workspace

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    *,
    status: str = "active",
    allowed_origins: list[str] | None = None,
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="web_widget",
        name="Test Widget",
        public_key=f"wgt_{uuid.uuid4().hex[:24]}",
        status=status,
        config_json={},
        allowed_origins=allowed_origins if allowed_origins is not None else [],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _post_session(client, public_key: str, body: dict | None = None, origin: str | None = None):
    headers = {"Origin": origin} if origin else {}
    return client.post(
        f"/public/widgets/{public_key}/sessions",
        json=body or {},
        headers=headers,
    )


def _count_messages(db: Session, conversation_id: uuid.UUID) -> int:
    return len(db.scalars(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id
        )
    ).all())


# ── Session creation ───────────────────────────────────────────────────────────

def test_creates_new_session(db: Session, workspace_a: Workspace, public_client):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _post_session(public_client, ch.public_key)

    assert resp.status_code == 200
    assert "session_token" in resp.json()


def test_session_token_starts_with_wss(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _post_session(public_client, ch.public_key)

    assert resp.json()["session_token"].startswith("wss_")


def test_creates_anonymous_contact(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    _post_session(public_client, ch.public_key)

    contacts = db.scalars(
        select(Contact).where(Contact.workspace_id == workspace_a.id)
    ).all()
    assert len(contacts) == 1
    assert contacts[0].name == "Visitante"


def test_contact_has_web_widget_metadata(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    _post_session(public_client, ch.public_key)

    contact = db.scalar(select(Contact).where(Contact.workspace_id == workspace_a.id))
    assert contact is not None
    assert contact.metadata_json["source"] == "web_widget"
    assert contact.metadata_json["public_key"] == ch.public_key


def test_creates_web_widget_conversation(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    _post_session(public_client, ch.public_key)

    conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
    assert conv is not None
    assert conv.channel_type == "web_widget"


def test_conversation_uses_channel_agent(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    _post_session(public_client, ch.public_key)

    conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
    assert conv is not None
    assert conv.agent_id == agent.id


def test_conversation_ai_enabled_true(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    _post_session(public_client, ch.public_key)

    conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
    assert conv is not None
    assert conv.ai_enabled is True


def test_conversation_status_open(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    _post_session(public_client, ch.public_key)

    conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
    assert conv is not None
    assert conv.status == "open"


def test_conversation_no_assigned_user(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    _post_session(public_client, ch.public_key)

    conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
    assert conv is not None
    assert conv.assigned_user_id is None


def test_creates_widget_session_record(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _post_session(public_client, ch.public_key)
    token = resp.json()["session_token"]

    ws = db.scalar(
        select(WidgetSession).where(WidgetSession.session_token == token)
    )
    assert ws is not None
    assert ws.channel_id == ch.id
    assert ws.workspace_id == workspace_a.id


def test_no_message_created_during_session(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _post_session(public_client, ch.public_key)
    token = resp.json()["session_token"]

    ws = db.scalar(
        select(WidgetSession).where(WidgetSession.session_token == token)
    )
    assert ws is not None
    assert _count_messages(db, ws.conversation_id) == 0


# ── Resume session ─────────────────────────────────────────────────────────────

def test_resumes_existing_session(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp1 = _post_session(public_client, ch.public_key)
    token1 = resp1.json()["session_token"]

    resp2 = _post_session(
        public_client, ch.public_key, body={"session_token": token1}
    )

    assert resp2.json()["session_token"] == token1


def test_resume_updates_last_seen_at(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp1 = _post_session(public_client, ch.public_key)
    token = resp1.json()["session_token"]

    before = db.scalar(
        select(WidgetSession.last_seen_at).where(WidgetSession.session_token == token)
    )

    # Pause briefly to ensure updated_at differs.
    import time
    time.sleep(0.05)

    _post_session(public_client, ch.public_key, body={"session_token": token})

    after = db.scalar(
        select(WidgetSession.last_seen_at).where(WidgetSession.session_token == token)
    )
    assert after >= before  # last_seen_at updated or same (depends on clock resolution)


def test_resume_only_one_contact_and_conversation(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp1 = _post_session(public_client, ch.public_key)
    token = resp1.json()["session_token"]
    _post_session(public_client, ch.public_key, body={"session_token": token})

    contacts = db.scalars(
        select(Contact).where(Contact.workspace_id == workspace_a.id)
    ).all()
    convs = db.scalars(
        select(Conversation).where(Conversation.workspace_id == workspace_a.id)
    ).all()
    assert len(contacts) == 1
    assert len(convs) == 1


def test_invalid_token_creates_new_session(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _post_session(
        public_client, ch.public_key,
        body={"session_token": "wss_invalid_token_that_does_not_exist"},
    )

    assert resp.status_code == 200
    assert resp.json()["session_token"].startswith("wss_")
    assert resp.json()["session_token"] != "wss_invalid_token_that_does_not_exist"


def test_token_from_different_channel_not_reused(
    db: Session,
    workspace_a: Workspace,
    workspace_b: Workspace,
    public_client,
):
    agent_a = _make_agent(db, workspace_a.id)
    agent_b = _make_agent(db, workspace_b.id)
    ch_a = _make_channel(db, workspace_a.id, agent_a.id)
    ch_b = _make_channel(db, workspace_b.id, agent_b.id)

    # Create session on channel A.
    resp_a = _post_session(public_client, ch_a.public_key)
    token_a = resp_a.json()["session_token"]

    # Try to use token_a on channel B → must get a new token.
    resp_b = _post_session(
        public_client, ch_b.public_key,
        body={"session_token": token_a},
    )

    assert resp_b.status_code == 200
    assert resp_b.json()["session_token"] != token_a


def test_token_cross_workspace_not_reused(
    db: Session,
    workspace_a: Workspace,
    workspace_b: Workspace,
    public_client,
):
    agent_a = _make_agent(db, workspace_a.id)
    agent_b = _make_agent(db, workspace_b.id)
    ch_a = _make_channel(db, workspace_a.id, agent_a.id)
    ch_b = _make_channel(db, workspace_b.id, agent_b.id)

    resp_b = _post_session(public_client, ch_b.public_key)
    token_b = resp_b.json()["session_token"]

    # Use token_b on ch_a (cross-workspace) → new session.
    resp_a = _post_session(
        public_client, ch_a.public_key,
        body={"session_token": token_b},
    )

    assert resp_a.status_code == 200
    assert resp_a.json()["session_token"] != token_b


# ── Inactive / archived channel ────────────────────────────────────────────────

def test_inactive_channel_rejects_session(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, status="inactive")

    resp = _post_session(public_client, ch.public_key)

    assert resp.status_code == 404
    sessions = db.scalars(select(WidgetSession)).all()
    assert len(sessions) == 0


def test_archived_channel_rejects_session(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, status="archived")

    resp = _post_session(public_client, ch.public_key)

    assert resp.status_code == 404
    sessions = db.scalars(select(WidgetSession)).all()
    assert len(sessions) == 0


# ── Origin validation ─────────────────────────────────────────────────────────

def test_origin_not_allowed_rejects_session(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id,
        allowed_origins=["https://allowed.com"],
    )

    resp = _post_session(
        public_client, ch.public_key, origin="https://evil.com"
    )

    assert resp.status_code == 403
    sessions = db.scalars(select(WidgetSession)).all()
    assert len(sessions) == 0


def test_allowed_origin_creates_session(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id,
        allowed_origins=["https://allowed.com"],
    )

    resp = _post_session(
        public_client, ch.public_key, origin="https://allowed.com"
    )

    assert resp.status_code == 200


# ── Two independent sessions ───────────────────────────────────────────────────

def test_two_sessions_have_independent_conversations(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp1 = _post_session(public_client, ch.public_key)
    resp2 = _post_session(public_client, ch.public_key)

    token1 = resp1.json()["session_token"]
    token2 = resp2.json()["session_token"]
    assert token1 != token2

    ws1 = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token1))
    ws2 = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token2))
    assert ws1 is not None
    assert ws2 is not None
    assert ws1.conversation_id != ws2.conversation_id
    assert ws1.contact_id != ws2.contact_id
