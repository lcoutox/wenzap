"""
Tests for Phase Auth.3 — cookie-based auth on protected routes.

These tests do NOT use dependency_overrides for get_current_user/get_current_workspace.
They exercise the real cookie auth stack end-to-end.
"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.sessions import revoke_session
from app.config import settings
from app.enums import MemberRole, MemberStatus
from app.models.auth_session import AuthSession
from app.models.workspace_member import WorkspaceMember
from tests.conftest import (
    _make_auth_session,
    _make_cookie_client,
    _make_user,
    _make_workspace,
)

COOKIE = settings.auth_cookie_name


# ── get_current_user — cookie auth ────────────────────────────────────────────


def test_no_cookie_returns_401(db: Session):
    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=True)
        r = client.get("/me")
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_invalid_cookie_returns_401(db: Session):
    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=True)
        client.cookies.set(COOKIE, "not-a-real-token")
        r = client.get("/me")
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_valid_cookie_authenticates(db: Session):
    user = _make_user(db, "cookie_auth@test.com", "Cookie Auth")
    _make_workspace(db, user, "cookie-auth-ws", "Cookie Auth WS")
    token = _make_auth_session(db, user)

    with _make_cookie_client(db, token) as client:
        r = client.get("/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "cookie_auth@test.com"
        assert body["workspace"]["slug"] == "cookie-auth-ws"


def test_revoked_session_returns_401(db: Session):
    user = _make_user(db, "revoked_cookie@test.com", "Revoked")
    _make_workspace(db, user, "revoked-ws", "Revoked WS")
    token = _make_auth_session(db, user)

    revoke_session(db, token)
    db.commit()

    with _make_cookie_client(db, token) as client:
        r = client.get("/me")
        assert r.status_code == 401


def test_expired_session_returns_401(db: Session):
    user = _make_user(db, "expired_cookie@test.com", "Expired")
    _make_workspace(db, user, "expired-ws", "Expired WS")
    token = _make_auth_session(db, user)

    # Manually expire the session
    session = db.query(AuthSession).filter_by(user_id=user.id).first()
    session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    with _make_cookie_client(db, token) as client:
        r = client.get("/me")
        assert r.status_code == 401


def test_last_seen_at_updates_on_authenticated_request(db: Session):
    user = _make_user(db, "lastseen_route@test.com", "LastSeen")
    _make_workspace(db, user, "lastseen-ws", "LastSeen WS")
    token = _make_auth_session(db, user)

    # Push last_seen_at into the past
    session = db.query(AuthSession).filter_by(user_id=user.id).first()
    session.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    with _make_cookie_client(db, token) as client:
        client.get("/me")

    db.expire(session)
    db.refresh(session)
    assert session.last_seen_at > datetime.now(timezone.utc) - timedelta(seconds=10)


# ── Protected routes with real cookie auth ────────────────────────────────────


def test_get_me_returns_user_and_workspace(db: Session):
    user = _make_user(db, "me_route@test.com", "Me Route")
    ws = _make_workspace(db, user, "me-route-ws", "Me Route WS")
    token = _make_auth_session(db, user)

    with _make_cookie_client(db, token) as client:
        r = client.get("/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "me_route@test.com"
        assert body["workspace"]["id"] == str(ws.id)
        assert body["role"] == MemberRole.owner.value


def test_get_agents_with_cookie_auth(db: Session):
    user = _make_user(db, "agents_route@test.com", "Agents Route")
    _make_workspace(db, user, "agents-ws", "Agents WS")
    token = _make_auth_session(db, user)

    with _make_cookie_client(db, token) as client:
        r = client.get("/agents")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


def test_get_knowledge_bases_with_cookie_auth(db: Session):
    user = _make_user(db, "kb_route@test.com", "KB Route")
    _make_workspace(db, user, "kb-ws", "KB WS")
    token = _make_auth_session(db, user)

    with _make_cookie_client(db, token) as client:
        r = client.get("/knowledge-bases")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Workspace isolation ───────────────────────────────────────────────────────


def test_workspace_resolved_from_session(db: Session):
    user = _make_user(db, "ws_resolve@test.com", "WS Resolve")
    ws = _make_workspace(db, user, "ws-resolve", "WS Resolve")
    token = _make_auth_session(db, user)

    with _make_cookie_client(db, token) as client:
        r = client.get("/me")
        assert r.json()["workspace"]["id"] == str(ws.id)


def test_x_workspace_id_header_selects_correct_workspace(db: Session):
    user = _make_user(db, "multi_ws@test.com", "Multi WS")
    _make_workspace(db, user, "ws-one", "WS One")
    ws2 = _make_workspace(db, user, "ws-two", "WS Two")
    token = _make_auth_session(db, user)

    with _make_cookie_client(db, token) as client:
        r = client.get("/me", headers={"X-Workspace-Id": str(ws2.id)})
        assert r.status_code == 200
        assert r.json()["workspace"]["id"] == str(ws2.id)


def test_x_workspace_id_for_other_user_returns_403(db: Session):
    user_a = _make_user(db, "iso_a@test.com", "Iso A")
    user_b = _make_user(db, "iso_b@test.com", "Iso B")
    _make_workspace(db, user_a, "iso-ws-a", "Iso WS A")
    ws_b = _make_workspace(db, user_b, "iso-ws-b", "Iso WS B")
    token_a = _make_auth_session(db, user_a)

    with _make_cookie_client(db, token_a) as client:
        # user_a tries to access user_b's workspace
        r = client.get("/me", headers={"X-Workspace-Id": str(ws_b.id)})
        assert r.status_code == 403


def test_user_without_workspace_returns_404(db: Session):
    # User with no workspace membership at all
    user = _make_user(db, "no_ws@test.com", "No WS")
    token = _make_auth_session(db, user)

    with _make_cookie_client(db, token) as client:
        r = client.get("/me")
        assert r.status_code == 404


# ── RBAC ─────────────────────────────────────────────────────────────────────


def test_owner_can_list_knowledge_bases(db: Session):
    owner = _make_user(db, "rbac_owner@test.com", "RBAC Owner")
    _make_workspace(db, owner, "rbac-ws", "RBAC WS")
    token = _make_auth_session(db, owner)

    with _make_cookie_client(db, token) as client:
        r = client.get("/knowledge-bases")
        assert r.status_code == 200


def test_viewer_member_can_list_but_not_create_knowledge_base(db: Session):
    owner = _make_user(db, "rbac_owner2@test.com", "RBAC Owner 2")
    viewer = _make_user(db, "rbac_viewer@test.com", "RBAC Viewer")
    ws = _make_workspace(db, owner, "rbac-ws2", "RBAC WS 2")

    # Add viewer as viewer-role member
    db.add(WorkspaceMember(
        workspace_id=ws.id,
        user_id=viewer.id,
        role=MemberRole.viewer,
        status=MemberStatus.active,
    ))
    db.commit()

    token = _make_auth_session(db, viewer)

    with _make_cookie_client(db, token) as client:
        # Viewer can list
        r = client.get("/knowledge-bases", headers={"X-Workspace-Id": str(ws.id)})
        assert r.status_code == 200

        # Viewer cannot create
        r = client.post(
            "/knowledge-bases",
            json={"name": "Viewer KB", "description": ""},
            headers={"X-Workspace-Id": str(ws.id)},
        )
        assert r.status_code == 403
