"""
Tests for Phase 5.4.6 — rate limiting on public widget endpoints.

POST /public/widgets/{key}/sessions:  5 per IP per 60s
POST /public/widgets/{key}/messages: 10 per session_token per 60s

These tests patch the rate_limiter store to control state without time dependency.
"""


from sqlalchemy.orm import Session

from app.models.workspace import Workspace
from tests.test_widget_messages import _make_agent_simple, _make_channel, _make_session

# ── Session rate limit ─────────────────────────────────────────────────────────

def test_session_rate_limit_allows_up_to_limit(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    for _ in range(5):
        resp = public_client.post(
            f"/public/widgets/{ch.public_key}/sessions",
            json={"session_token": None},
        )
        assert resp.status_code == 200


def test_session_rate_limit_blocks_on_6th_request(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    for _ in range(5):
        public_client.post(
            f"/public/widgets/{ch.public_key}/sessions",
            json={"session_token": None},
        )

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={"session_token": None},
    )
    assert resp.status_code == 429


def test_session_rate_limit_returns_retry_after(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    for _ in range(5):
        public_client.post(f"/public/widgets/{ch.public_key}/sessions", json={})

    resp = public_client.post(f"/public/widgets/{ch.public_key}/sessions", json={})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


# ── Message rate limit ─────────────────────────────────────────────────────────

def test_message_rate_limit_allows_up_to_limit(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ws = _make_session(db, ch, workspace_a.id)

    for i in range(10):
        resp = public_client.post(
            f"/public/widgets/{ch.public_key}/messages",
            json={"content": f"msg {i}"},
            headers={"X-Session-Token": ws.session_token},
        )
        assert resp.status_code == 201


def test_message_rate_limit_blocks_on_11th_request(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ws = _make_session(db, ch, workspace_a.id)

    for i in range(10):
        public_client.post(
            f"/public/widgets/{ch.public_key}/messages",
            json={"content": f"msg {i}"},
            headers={"X-Session-Token": ws.session_token},
        )

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/messages",
        json={"content": "one too many"},
        headers={"X-Session-Token": ws.session_token},
    )
    assert resp.status_code == 429


def test_message_rate_limit_is_per_session_token(
    db: Session, workspace_a: Workspace, public_client
):
    """Two different sessions have independent rate limit buckets."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ws1 = _make_session(db, ch, workspace_a.id)
    ws2 = _make_session(db, ch, workspace_a.id)

    for i in range(10):
        public_client.post(
            f"/public/widgets/{ch.public_key}/messages",
            json={"content": f"msg {i}"},
            headers={"X-Session-Token": ws1.session_token},
        )

    # ws2 should still work
    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/messages",
        json={"content": "from session 2"},
        headers={"X-Session-Token": ws2.session_token},
    )
    assert resp.status_code == 201


def test_message_rate_limit_missing_token_skips_check(
    db: Session, workspace_a: Workspace, public_client
):
    """Missing session token → 401 (not 429) regardless of rate limit state."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/messages",
        json={"content": "hello"},
    )
    assert resp.status_code == 401
