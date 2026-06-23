"""
Tests for Playground Sessions API.

Endpoints under test:
  GET    /agents/{agent_id}/playground/sessions
  POST   /agents/{agent_id}/playground/sessions
  GET    /agents/{agent_id}/playground/sessions/{session_id}
  DELETE /agents/{agent_id}/playground/sessions/{session_id}

LLM policy:
  Tests that need messages use mock LLM (never calls Anthropic API).

Isolation policy:
  All requests filtered by workspace_id + agent_id so cross-workspace/cross-agent
  access always returns 404, not 403 — to not leak resource existence.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.agent_playground_session import AgentPlaygroundSession
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client, _make_user
from tests.test_agent_test import (
    _full_setup,
    _get_messages,
    _get_sessions,
    _mock_llm_response,
    _post_test,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_viewer(db: Session, ws):
    viewer = _make_user(db, f"viewer-{uuid.uuid4().hex[:6]}@test.com", "Viewer")
    db.add(WorkspaceMember(
        workspace_id=ws.id,
        user_id=viewer.id,
        role=MemberRole.viewer,
        status=MemberStatus.active,
    ))
    db.commit()
    return viewer


def _make_member_with_role(db: Session, ws, role: MemberRole):
    user = _make_user(db, f"{role.value}-{uuid.uuid4().hex[:6]}@test.com", role.value.capitalize())
    db.add(WorkspaceMember(
        workspace_id=ws.id,
        user_id=user.id,
        role=role,
        status=MemberStatus.active,
    ))
    db.commit()
    return user


def _create_session(client, agent_id):
    return client.post(f"/agents/{agent_id}/playground/sessions", json={})


def _list_sessions(client, agent_id):
    return client.get(f"/agents/{agent_id}/playground/sessions")


def _get_session(client, agent_id, session_id):
    return client.get(f"/agents/{agent_id}/playground/sessions/{session_id}")


def _delete_session(client, agent_id, session_id):
    return client.delete(f"/agents/{agent_id}/playground/sessions/{session_id}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Create session — RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_create_session_as_owner_returns_201(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r = _create_session(client, agent.id)

    assert r.status_code == 201
    body = r.json()
    assert body["agent_id"] == str(agent.id)
    assert body["workspace_id"] == str(ws.id)
    assert body["title"] == "Nova conversa"
    assert "id" in body


def test_create_session_as_admin_returns_201(db):
    user, ws, agent, *_ = _full_setup(db)
    admin = _make_member_with_role(db, ws, MemberRole.admin)

    with _make_client(db, admin, ws) as client:
        r = _create_session(client, agent.id)

    assert r.status_code == 201


def test_create_session_as_member_returns_201(db):
    user, ws, agent, *_ = _full_setup(db)
    member = _make_member_with_role(db, ws, MemberRole.member)

    with _make_client(db, member, ws) as client:
        r = _create_session(client, agent.id)

    assert r.status_code == 201


def test_viewer_cannot_create_session(db):
    user, ws, agent, *_ = _full_setup(db)
    viewer = _make_viewer(db, ws)

    with _make_client(db, viewer, ws) as client:
        r = _create_session(client, agent.id)

    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Create session — default state
# ═══════════════════════════════════════════════════════════════════════════════

def test_new_session_has_default_title(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r = _create_session(client, agent.id)

    assert r.json()["title"] == "Nova conversa"


def test_new_session_has_correct_ids(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r = _create_session(client, agent.id)

    body = r.json()
    assert body["workspace_id"] == str(ws.id)
    assert body["agent_id"] == str(agent.id)
    assert body["user_id"] == str(user.id)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. List sessions
# ═══════════════════════════════════════════════════════════════════════════════

def test_list_sessions_empty(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r = _list_sessions(client, agent.id)

    assert r.status_code == 200
    assert r.json() == []


def test_list_sessions_returns_created_sessions(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        _create_session(client, agent.id)
        _create_session(client, agent.id)
        r = _list_sessions(client, agent.id)

    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_sessions_excludes_other_agent(db):
    """Sessions from a different agent in the same workspace are not returned."""
    user, ws, agent, *_ = _full_setup(db)
    _, ws2, agent2, *_ = _full_setup(db)

    # Create sessions for agent2 in a different workspace context
    with _make_client(db, user, ws) as client:
        _create_session(client, agent.id)

    # Sessions for agent2 should not bleed into agent's list
    with _make_client(db, user, ws) as client:
        r = _list_sessions(client, agent.id)

    sessions = r.json()
    assert all(s["agent_id"] == str(agent.id) for s in sessions)


def test_list_sessions_excludes_other_workspace(db):
    """Sessions from workspace B must not appear when querying workspace A."""
    user_a, ws_a, agent_a, *_ = _full_setup(db)
    user_b, ws_b, agent_b, *_ = _full_setup(db)

    # Create a session in workspace B
    with _make_client(db, user_b, ws_b) as client:
        _create_session(client, agent_b.id)

    # workspace A should have no sessions
    with _make_client(db, user_a, ws_a) as client:
        r = _list_sessions(client, agent_a.id)

    assert r.json() == []


def test_viewer_cannot_list_sessions(db):
    user, ws, agent, *_ = _full_setup(db)
    viewer = _make_viewer(db, ws)

    with _make_client(db, viewer, ws) as client:
        r = _list_sessions(client, agent.id)

    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 4. List sessions — ordering
# ═══════════════════════════════════════════════════════════════════════════════

def test_list_sessions_ordered_by_updated_at_desc(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r_old = _create_session(client, agent.id)
        r_new = _create_session(client, agent.id)

    session_id_old = uuid.UUID(r_old.json()["id"])
    session_id_new = uuid.UUID(r_new.json()["id"])

    # Force session_old's updated_at into the past so ordering is deterministic
    db.execute(
        update(AgentPlaygroundSession)
        .where(AgentPlaygroundSession.id == session_id_old)
        .values(updated_at=datetime.now(timezone.utc) - timedelta(hours=1))
    )
    db.commit()

    with _make_client(db, user, ws) as client:
        r = _list_sessions(client, agent.id)

    sessions = r.json()
    assert len(sessions) == 2
    assert sessions[0]["id"] == str(session_id_new)
    assert sessions[1]["id"] == str(session_id_old)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Get session with messages
# ═══════════════════════════════════════════════════════════════════════════════

def test_get_session_empty_messages(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r_create = _create_session(client, agent.id)
        r_get = _get_session(client, agent.id, r_create.json()["id"])

    assert r_get.status_code == 200
    body = r_get.json()
    assert body["id"] == r_create.json()["id"]
    assert body["messages"] == []


def test_get_session_returns_messages_in_order(db):
    user, ws, agent, *_ = _full_setup(db)

    # Create session and send two messages
    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
    session_id = r_sess.json()["id"]

    with patch("app.llm.client.complete", return_value=_mock_llm_response("Reply 1")):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id, message="Hello", session_id=session_id)

    with patch("app.llm.client.complete", return_value=_mock_llm_response("Reply 2")):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id, message="How are you?", session_id=session_id)

    with _make_client(db, user, ws) as client:
        r = _get_session(client, agent.id, session_id)

    messages = r.json()["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "How are you?"
    assert messages[3]["role"] == "assistant"


def test_get_session_message_fields(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
    session_id = r_sess.json()["id"]

    with patch("app.llm.client.complete", return_value=_mock_llm_response("Hi!")):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id, message="Hey", session_id=session_id)

    with _make_client(db, user, ws) as client:
        r = _get_session(client, agent.id, session_id)

    messages = r.json()["messages"]
    user_msg = next(m for m in messages if m["role"] == "user")
    asst_msg = next(m for m in messages if m["role"] == "assistant")

    assert user_msg["content"] == "Hey"
    assert user_msg["agent_test_run_id"] is None

    assert asst_msg["content"] == "Hi!"
    assert asst_msg["agent_test_run_id"] is not None


def test_get_session_other_workspace_returns_404(db):
    user_a, ws_a, agent_a, *_ = _full_setup(db)
    user_b, ws_b, agent_b, *_ = _full_setup(db)

    with _make_client(db, user_b, ws_b) as client:
        r = _create_session(client, agent_b.id)
    session_id_b = r.json()["id"]

    with _make_client(db, user_a, ws_a) as client:
        r = _get_session(client, agent_a.id, session_id_b)

    assert r.status_code == 404


def test_get_session_other_agent_returns_404(db):
    user, ws, agent, *_ = _full_setup(db)
    _, ws2, agent2, *_ = _full_setup(db)

    # Create a session for agent2 directly in DB
    session = AgentPlaygroundSession(
        id=uuid.uuid4(),
        workspace_id=ws2.id,
        agent_id=agent2.id,
        user_id=user.id,
        title="Nova conversa",
    )
    db.add(session)
    db.commit()

    with _make_client(db, user, ws) as client:
        # Try to fetch session from agent2 using agent's endpoint
        r = _get_session(client, agent.id, str(session.id))

    assert r.status_code == 404


def test_viewer_cannot_get_session(db):
    user, ws, agent, *_ = _full_setup(db)
    viewer = _make_viewer(db, ws)

    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
    session_id = r_sess.json()["id"]

    with _make_client(db, viewer, ws) as client:
        r = _get_session(client, agent.id, session_id)

    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Delete session
# ═══════════════════════════════════════════════════════════════════════════════

def test_delete_session_returns_204(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
        r_del = _delete_session(client, agent.id, r_sess.json()["id"])

    assert r_del.status_code == 204


def test_get_after_delete_returns_404(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
        session_id = r_sess.json()["id"]
        _delete_session(client, agent.id, session_id)
        r = _get_session(client, agent.id, session_id)

    assert r.status_code == 404


def test_delete_session_cascades_messages(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
    session_id = uuid.UUID(r_sess.json()["id"])

    with patch("app.llm.client.complete", return_value=_mock_llm_response("Hello")):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id, message="Hi", session_id=str(session_id))

    # Verify messages exist
    assert len(_get_messages(db, session_id)) == 2

    with _make_client(db, user, ws) as client:
        _delete_session(client, agent.id, str(session_id))

    # Messages must be gone
    assert len(_get_messages(db, session_id)) == 0


def test_delete_session_other_workspace_returns_404(db):
    user_a, ws_a, agent_a, *_ = _full_setup(db)
    user_b, ws_b, agent_b, *_ = _full_setup(db)

    with _make_client(db, user_b, ws_b) as client:
        r = _create_session(client, agent_b.id)
    session_id_b = r.json()["id"]

    with _make_client(db, user_a, ws_a) as client:
        r = _delete_session(client, agent_a.id, session_id_b)

    assert r.status_code == 404


def test_delete_session_other_agent_returns_404(db):
    user, ws, agent, *_ = _full_setup(db)
    _, ws2, agent2, *_ = _full_setup(db)

    session = AgentPlaygroundSession(
        id=uuid.uuid4(),
        workspace_id=ws2.id,
        agent_id=agent2.id,
        user_id=user.id,
        title="Nova conversa",
    )
    db.add(session)
    db.commit()

    with _make_client(db, user, ws) as client:
        r = _delete_session(client, agent.id, str(session.id))

    assert r.status_code == 404


def test_viewer_cannot_delete_session(db):
    user, ws, agent, *_ = _full_setup(db)
    viewer = _make_viewer(db, ws)

    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
    session_id = r_sess.json()["id"]

    with _make_client(db, viewer, ws) as client:
        r = _delete_session(client, agent.id, session_id)

    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# 7. touch_session — updated_at advances on new message
# ═══════════════════════════════════════════════════════════════════════════════

def test_sending_message_touches_session_updated_at(db):
    user, ws, agent, *_ = _full_setup(db)

    with _make_client(db, user, ws) as client:
        r_sess = _create_session(client, agent.id)
    session_id = uuid.UUID(r_sess.json()["id"])

    # Record initial updated_at
    sessions = _get_sessions(db, agent.id)
    initial_updated_at = sessions[0].updated_at

    # Push it back so the update is guaranteed to be detectable
    db.execute(
        update(AgentPlaygroundSession)
        .where(AgentPlaygroundSession.id == session_id)
        .values(updated_at=initial_updated_at - timedelta(hours=1))
    )
    db.commit()

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user, ws) as client:
            _post_test(client, agent.id, message="Hi", session_id=str(session_id))

    db.expire_all()
    sessions_after = _get_sessions(db, agent.id)
    session_after = next(s for s in sessions_after if s.id == session_id)
    assert session_after.updated_at > initial_updated_at - timedelta(hours=1)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Tenant isolation — cross-workspace POST /test with session_id
# ═══════════════════════════════════════════════════════════════════════════════

def test_cannot_use_other_workspace_session_in_test(db):
    user_a, ws_a, agent_a, *_ = _full_setup(db)
    user_b, ws_b, agent_b, *_ = _full_setup(db)

    # Create session in workspace B
    with _make_client(db, user_b, ws_b) as client:
        r = _create_session(client, agent_b.id)
    session_id_b = r.json()["id"]

    # Try to use it from workspace A
    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user_a, ws_a) as client:
            r = _post_test(client, agent_a.id, session_id=session_id_b)

    assert r.status_code == 404


def test_sessions_are_isolated_between_workspaces(db):
    user_a, ws_a, agent_a, *_ = _full_setup(db)
    user_b, ws_b, agent_b, *_ = _full_setup(db)

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user_a, ws_a) as client:
            _post_test(client, agent_a.id)

    with patch("app.llm.client.complete", return_value=_mock_llm_response()):
        with _make_client(db, user_b, ws_b) as client:
            _post_test(client, agent_b.id)

    # Each workspace has exactly 1 session, no bleed-through
    sessions_a = _get_sessions(db, agent_a.id)
    sessions_b = _get_sessions(db, agent_b.id)
    assert len(sessions_a) == 1
    assert len(sessions_b) == 1
    assert sessions_a[0].workspace_id == ws_a.id
    assert sessions_b[0].workspace_id == ws_b.id
