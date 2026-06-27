"""
Tests for Phase Auth.2 — first-party auth backend.

Uses the same test DB and conftest fixtures.
Auth endpoints are unauthenticated by Clerk; they use cookies instead.
"""

import hashlib
import secrets
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.password import verify_password
from app.auth.sessions import get_session_by_token, hash_session_token, revoke_session
from app.database import get_db
from app.main import app
from app.models.auth_session import AuthSession
from app.models.password_reset_token import PasswordResetToken
from app.models.plan import Plan
from app.models.user import User
from app.models.user_auth_credential import UserAuthCredential
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember

COOKIE_NAME = "wenzap_session"

RESET_BODY = {"token": "placeholder", "new_password": "newpassword123"}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def starter_plan(db: Session) -> Plan:
    plan = Plan(
        code="starter",
        name="Starter",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=1,
        knowledge_bases_limit=1,
        users_limit=3,
        pipelines_limit=1,
        integrations_limit=0,
        monthly_ai_credits=1000,
        monthly_conversations=500,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@contextmanager
def _auth_client(db: Session):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()


def _signup(client: TestClient, email: str, password: str, name: str | None = None):
    payload: dict = {"email": email, "password": password}
    if name:
        payload["name"] = name
    return client.post("/auth/signup", json=payload)


def _make_reset_token(db: Session, user: User) -> str:
    """Insert a valid reset token and return the raw (pre-hash) value."""
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    db.add(PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    db.commit()
    return raw


# ── Signup ────────────────────────────────────────────────────────────────────


def test_signup_creates_user(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "alice@example.com", "password123", "Alice")
        assert r.status_code == 201
        body = r.json()
        assert body["user"]["email"] == "alice@example.com"
        assert body["user"]["name"] == "Alice"
        assert "workspace" in body

        user = db.query(User).filter_by(email="alice@example.com").first()
        assert user is not None
        assert user.external_id is None


def test_signup_creates_credential(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "bob@example.com", "password123")

    user = db.query(User).filter_by(email="bob@example.com").first()
    cred = db.query(UserAuthCredential).filter_by(user_id=user.id).first()
    assert cred is not None
    assert cred.password_hash != "password123"
    assert cred.password_hash.startswith("$argon2")


def test_signup_creates_workspace_and_member(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "carol@example.com", "password123", "Carol")
        ws_id = r.json()["workspace"]["id"]

    workspace = db.query(Workspace).filter_by(id=ws_id).first()
    assert workspace is not None

    user = db.query(User).filter_by(email="carol@example.com").first()
    member = db.query(WorkspaceMember).filter_by(
        workspace_id=workspace.id, user_id=user.id
    ).first()
    assert member is not None
    assert member.role == "owner"


def test_signup_sets_cookie(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "dave@example.com", "password123")
        assert COOKIE_NAME in r.cookies


def test_signup_creates_session(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "eve@example.com", "password123")
        token = r.cookies[COOKIE_NAME]

    session = get_session_by_token(db, token)
    assert session is not None


def test_signup_duplicate_email_returns_409(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "dup@example.com", "password123")
        r = _signup(client, "dup@example.com", "password456")
        assert r.status_code == 409


def test_signup_weak_password_returns_422(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "weak@example.com", "short")
        assert r.status_code == 422


def test_signup_normalizes_email_lowercase(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "UPPER@EXAMPLE.COM", "password123")
        assert r.json()["user"]["email"] == "upper@example.com"

    user = db.query(User).filter_by(email="upper@example.com").first()
    assert user is not None


def test_signup_uses_email_prefix_as_name_when_missing(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "noname@example.com", "password123")
        assert r.json()["user"]["name"] == "noname"


# ── Login ─────────────────────────────────────────────────────────────────────


def test_login_valid_sets_cookie(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "login@example.com", "password123")
        r = client.post(
            "/auth/login", json={"email": "login@example.com", "password": "password123"}
        )
        assert r.status_code == 200
        assert COOKIE_NAME in r.cookies


def test_login_wrong_password_returns_401(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "wrongpwd@example.com", "password123")
        r = client.post(
            "/auth/login", json={"email": "wrongpwd@example.com", "password": "wrongpassword"}
        )
        assert r.status_code == 401
        assert r.json()["detail"]  # must be generic, not reveal user existence


def test_login_nonexistent_email_returns_401(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = client.post(
            "/auth/login", json={"email": "ghost@example.com", "password": "password123"}
        )
        assert r.status_code == 401


def test_login_wrong_password_does_not_create_session(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "nosession@example.com", "password123")
        client.post("/auth/login", json={"email": "nosession@example.com", "password": "wrong"})

    user = db.query(User).filter_by(email="nosession@example.com").first()
    sessions = db.query(AuthSession).filter_by(user_id=user.id).all()
    assert len(sessions) == 1  # only the signup session


# ── Logout ────────────────────────────────────────────────────────────────────


def test_logout_revokes_session(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "logout@example.com", "password123")
        token = r.cookies[COOKIE_NAME]
        client.post("/auth/logout")

    session = get_session_by_token(db, token)
    assert session is None


def test_logout_clears_cookie(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "logoutcookie@example.com", "password123")
        r = client.post("/auth/logout")
        assert r.status_code == 204


def test_logout_without_session_does_not_raise(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = client.post("/auth/logout")
        assert r.status_code == 204


# ── /me ───────────────────────────────────────────────────────────────────────


def test_me_without_cookie_returns_401(db: Session):
    with _auth_client(db) as client:
        r = client.get("/auth/me")
        assert r.status_code == 401


def test_me_with_valid_cookie_returns_user_and_workspace(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        signup_r = _signup(client, "me@example.com", "password123", "Me User")
        token = signup_r.cookies[COOKIE_NAME]
        client.cookies.set(COOKIE_NAME, token)
        r = client.get("/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["email"] == "me@example.com"
        assert "workspace" in body


def test_me_with_revoked_session_returns_401(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "revoked@example.com", "password123")
        token = r.cookies[COOKIE_NAME]
        revoke_session(db, token)
        db.commit()
        client.cookies.set(COOKIE_NAME, token)
        r = client.get("/auth/me")
        assert r.status_code == 401


def test_me_with_expired_session_returns_401(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "expired@example.com", "password123")
        token = r.cookies[COOKIE_NAME]

    user = db.query(User).filter_by(email="expired@example.com").first()
    session = db.query(AuthSession).filter_by(user_id=user.id).first()
    session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()

    with _auth_client(db) as client:
        client.cookies.set(COOKIE_NAME, token)
        r = client.get("/auth/me")
        assert r.status_code == 401


def test_me_updates_last_seen_at(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "lastseen@example.com", "password123")
        token = r.cookies[COOKIE_NAME]

    user = db.query(User).filter_by(email="lastseen@example.com").first()
    session_before = db.query(AuthSession).filter_by(user_id=user.id).first()

    # Push last_seen_at into the past so we can detect an update
    session_before.last_seen_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    db.commit()

    with _auth_client(db) as client:
        client.cookies.set(COOKIE_NAME, token)
        client.get("/auth/me")

    db.expire(session_before)
    db.refresh(session_before)
    assert session_before.last_seen_at > datetime.now(timezone.utc) - timedelta(seconds=5)


# ── Forgot / Reset password ───────────────────────────────────────────────────


def test_forgot_password_always_returns_200(db: Session):
    with _auth_client(db) as client:
        r = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
        assert r.status_code == 200


def test_forgot_password_creates_reset_token(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "reset@example.com", "password123")
        client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    user = db.query(User).filter_by(email="reset@example.com").first()
    token_row = db.query(PasswordResetToken).filter_by(user_id=user.id).first()
    assert token_row is not None
    assert token_row.used_at is None
    assert token_row.expires_at > datetime.now(timezone.utc)


def test_reset_password_valid_token_updates_hash(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "resetpwd@example.com", "oldpassword123")

    user = db.query(User).filter_by(email="resetpwd@example.com").first()
    raw_token = _make_reset_token(db, user)

    with _auth_client(db) as client:
        r = client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "newpassword123"},
        )
        assert r.status_code == 200

    cred = db.query(UserAuthCredential).filter_by(user_id=user.id).first()
    assert verify_password("newpassword123", cred.password_hash)
    assert not verify_password("oldpassword123", cred.password_hash)


def test_reset_password_marks_token_as_used(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "markused@example.com", "password123")

    user = db.query(User).filter_by(email="markused@example.com").first()
    raw_token = _make_reset_token(db, user)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    with _auth_client(db) as client:
        client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "newpassword123"},
        )

    token_row = db.query(PasswordResetToken).filter_by(token_hash=token_hash).first()
    assert token_row.used_at is not None


def test_reset_password_used_token_fails(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "usedtoken@example.com", "password123")

    user = db.query(User).filter_by(email="usedtoken@example.com").first()
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    db.add(PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used_at=datetime.now(timezone.utc),  # already used
    ))
    db.commit()

    with _auth_client(db) as client:
        r = client.post(
            "/auth/reset-password", json={"token": raw, "new_password": "newpassword123"}
        )
        assert r.status_code == 400


def test_reset_password_expired_token_fails(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "expiredtoken@example.com", "password123")

    user = db.query(User).filter_by(email="expiredtoken@example.com").first()
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    db.add(PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # expired
    ))
    db.commit()

    with _auth_client(db) as client:
        r = client.post(
            "/auth/reset-password", json={"token": raw, "new_password": "newpassword123"}
        )
        assert r.status_code == 400


def test_reset_password_revokes_existing_sessions(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "revokeonsreset@example.com", "password123")
        old_token = r.cookies[COOKIE_NAME]

    user = db.query(User).filter_by(email="revokeonsreset@example.com").first()
    raw_token = _make_reset_token(db, user)

    with _auth_client(db) as client:
        client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "newpassword123"},
        )

    old_session = get_session_by_token(db, old_token)
    assert old_session is None


def test_after_reset_old_password_fails_new_works(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "passchg@example.com", "oldpassword123")

    user = db.query(User).filter_by(email="passchg@example.com").first()
    raw_token = _make_reset_token(db, user)

    with _auth_client(db) as client:
        client.post(
            "/auth/reset-password",
            json={"token": raw_token, "new_password": "newpassword123"},
        )
        r_old = client.post(
            "/auth/login",
            json={"email": "passchg@example.com", "password": "oldpassword123"},
        )
        r_new = client.post(
            "/auth/login",
            json={"email": "passchg@example.com", "password": "newpassword123"},
        )
        assert r_old.status_code == 401
        assert r_new.status_code == 200


# ── Session security ──────────────────────────────────────────────────────────


def test_session_token_stored_hashed(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        r = _signup(client, "hashcheck@example.com", "password123")
        raw_token = r.cookies[COOKIE_NAME]

    # Raw token must NOT be in the DB
    all_sessions = db.query(AuthSession).all()
    for s in all_sessions:
        assert s.session_token_hash != raw_token

    # The hash must be in the DB
    expected_hash = hash_session_token(raw_token)
    match = db.query(AuthSession).filter_by(session_token_hash=expected_hash).first()
    assert match is not None


def test_reset_token_stored_hashed(db: Session, starter_plan: Plan):
    with _auth_client(db) as client:
        _signup(client, "resethash@example.com", "password123")
        client.post("/auth/forgot-password", json={"email": "resethash@example.com"})

    user = db.query(User).filter_by(email="resethash@example.com").first()
    token_row = db.query(PasswordResetToken).filter_by(user_id=user.id).first()
    assert token_row is not None
    # Hash field must be SHA-256 hex (64 chars), not the raw urlsafe token
    assert len(token_row.token_hash) == 64
    assert all(c in "0123456789abcdef" for c in token_row.token_hash)
