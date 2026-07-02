"""
Tests for Auth.6 — Email Verification.

Covers:
1.  Signup creates user with email_verified=False.
2.  Signup generates an email verification token.
3.  Signup normalizes email to lowercase.
4.  Signup rejects duplicate email (case-insensitive, already normalized).
5.  Signup calls email service (fake — no real SendGrid call).
6.  verify-email with valid token marks user as verified.
7.  verify-email with invalid token fails.
8.  verify-email with expired token fails.
9.  verify-email with already-used token fails.
10. resend generates a new token (and invalidates old one).
11. resend returns success when user already verified.
12. Unverified user is blocked on a sensitive endpoint (agents).
13. Verified user can access sensitive endpoint.
14. /auth/me returns email_verified field.
15. Login response includes email_verified=False for unverified user.
16. No test sends a real email (FakeEmailService is always used).
"""

import hashlib
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.email_verification_token import EmailVerificationToken
from app.models.plan import Plan
from app.models.user import User
from app.models.user_auth_credential import UserAuthCredential
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.email_service import FakeEmailService, override_email_service, reset_email_service

COOKIE_NAME = "wenzap_session"


# ── Helpers ───────────────────────────────────────────────────────────────────

@contextmanager
def _real_client(db: Session):
    """Client that uses the real auth stack (cookie-based), no dependency override."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def fake_email() -> FakeEmailService:
    """Inject FakeEmailService and reset after test."""
    svc = FakeEmailService()
    override_email_service(svc)
    yield svc
    reset_email_service()


@pytest.fixture()
def starter_plan(db: Session) -> Plan:
    from sqlalchemy import select as _sel
    p = db.scalar(_sel(Plan).where(Plan.code == "starter"))
    if p is None:
        p = Plan(
            code="starter", name="Starter", monthly_price_cents=0, currency="BRL",
            agents_limit=1, knowledge_bases_limit=1, users_limit=3,
            pipelines_limit=1, integrations_limit=0, monthly_ai_credits=200,
            monthly_conversations=500, is_active=True, is_public=True, sort_order=10,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


SIGNUP_BODY = {
    "name": "Tester",
    "email": "tester@example.com",
    "password": "password123",
}


# ── Tests ─────────────────────────────────────────────────────────────────────

# 1. Signup creates user with email_verified=False
def test_signup_creates_user_with_email_not_verified(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        r = client.post("/auth/signup", json=SIGNUP_BODY)
    assert r.status_code == 201
    user = db.scalar(select(User).where(User.email == "tester@example.com"))
    assert user is not None
    assert user.email_verified is False
    assert user.email_verified_at is None


# 2. Signup generates verification token
def test_signup_generates_verification_token(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
    user = db.scalar(select(User).where(User.email == "tester@example.com"))
    tokens = db.scalars(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    ).all()
    assert len(tokens) >= 1
    assert tokens[0].used_at is None
    assert tokens[0].expires_at > datetime.now(timezone.utc)


# 3. Signup normalizes email to lowercase
def test_signup_normalizes_email_lowercase(db: Session, starter_plan, fake_email):
    body = {**SIGNUP_BODY, "email": "Tester@EXAMPLE.COM"}
    with _real_client(db) as client:
        r = client.post("/auth/signup", json=body)
    assert r.status_code == 201
    user = db.scalar(select(User).where(User.email == "tester@example.com"))
    assert user is not None


# 4. Signup rejects duplicate email (case-insensitive)
def test_signup_rejects_duplicate_email(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        r1 = client.post("/auth/signup", json=SIGNUP_BODY)
        assert r1.status_code == 201
        r2 = client.post("/auth/signup", json={**SIGNUP_BODY, "email": "TESTER@EXAMPLE.COM"})
    assert r2.status_code == 409


# 5. Signup calls email service (fake — no real SendGrid)
def test_signup_sends_verification_email(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
    assert len(fake_email.sent) == 1
    assert fake_email.sent[0]["to"] == "tester@example.com"
    assert "Confirme" in fake_email.sent[0]["subject"]


# 6. verify-email with valid token marks user as verified
def test_verify_email_with_valid_token(db: Session, starter_plan, fake_email):
    import hashlib, secrets  # noqa: E401
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)

    user = db.scalar(select(User).where(User.email == "tester@example.com"))
    # Extract raw token from the email link sent
    sent_html = fake_email.sent[0]["html"]
    import re
    match = re.search(r"token=([A-Za-z0-9_\-]+)", sent_html)
    assert match, "Token not found in email"
    raw_token = match.group(1)

    with _real_client(db) as client:
        r = client.post("/auth/verify-email", json={"token": raw_token})
    assert r.status_code == 200

    db.refresh(user)
    assert user.email_verified is True
    assert user.email_verified_at is not None


# 7. verify-email with invalid token fails
def test_verify_email_with_invalid_token(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        r = client.post("/auth/verify-email", json={"token": "invalid_token_xyz"})
    assert r.status_code == 400


# 8. verify-email with expired token fails
def test_verify_email_with_expired_token(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)

    user = db.scalar(select(User).where(User.email == "tester@example.com"))
    token_record = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    # Force expire
    token_record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()

    import hashlib, secrets  # noqa: E401
    import re
    match = re.search(r"token=([A-Za-z0-9_\-]+)", fake_email.sent[0]["html"])
    raw_token = match.group(1)

    with _real_client(db) as client:
        r = client.post("/auth/verify-email", json={"token": raw_token})
    assert r.status_code == 400


# 9. verify-email with already-used token fails
def test_verify_email_with_used_token(db: Session, starter_plan, fake_email):
    import re
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)

    match = re.search(r"token=([A-Za-z0-9_\-]+)", fake_email.sent[0]["html"])
    raw_token = match.group(1)

    with _real_client(db) as client:
        r1 = client.post("/auth/verify-email", json={"token": raw_token})
        assert r1.status_code == 200
        r2 = client.post("/auth/verify-email", json={"token": raw_token})
    assert r2.status_code == 400


# 10. resend generates new token (and invalidates old one)
def test_resend_generates_new_token(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        resp = client.post("/auth/signup", json=SIGNUP_BODY)
        cookie = resp.cookies.get(COOKIE_NAME)
        assert cookie

        r = client.post("/auth/resend-verification-email")
    assert r.status_code == 200
    assert len(fake_email.sent) == 2  # signup + resend

    user = db.scalar(select(User).where(User.email == "tester@example.com"))
    tokens = db.scalars(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    ).all()
    # Only the latest token should be unused; the old one was invalidated
    unused = [t for t in tokens if t.used_at is None]
    assert len(unused) == 1


# 11. resend returns success when user already verified
def test_resend_noop_when_already_verified(db: Session, starter_plan, fake_email):
    import re
    with _real_client(db) as client:
        resp = client.post("/auth/signup", json=SIGNUP_BODY)
        match = re.search(r"token=([A-Za-z0-9_\-]+)", fake_email.sent[0]["html"])
        raw_token = match.group(1)
        client.post("/auth/verify-email", json={"token": raw_token})

        r = client.post("/auth/resend-verification-email")
    assert r.status_code == 200
    assert r.json()["message"] == "E-mail já verificado."
    assert len(fake_email.sent) == 1  # only the initial signup email


# 12. Unverified user blocked on sensitive endpoints (agents, conversations, contacts)
def test_unverified_user_blocked_on_agents(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
        r = client.get("/agents")
    assert r.status_code == 403
    assert "verificado" in r.json()["detail"].lower()


def test_unverified_user_blocked_on_conversations(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
        r = client.get("/conversations")
    assert r.status_code == 403


def test_unverified_user_blocked_on_contacts(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
        r = client.get("/contacts")
    assert r.status_code == 403


def test_unverified_user_blocked_on_onboarding(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
        r = client.get("/onboarding")
    assert r.status_code == 403


# 13. Verified user can access agents endpoint
def test_verified_user_can_access_agents(db: Session, starter_plan, fake_email):
    import re
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
        match = re.search(r"token=([A-Za-z0-9_\-]+)", fake_email.sent[0]["html"])
        raw_token = match.group(1)
        client.post("/auth/verify-email", json={"token": raw_token})
        r = client.get("/agents")
    assert r.status_code == 200


# 14. /auth/me returns email_verified field
def test_me_returns_email_verified_field(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
        r = client.get("/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert "email_verified" in data["user"]
    assert data["user"]["email_verified"] is False


# 15. Login response includes email_verified for unverified user
def test_login_returns_email_verified_false(db: Session, starter_plan, fake_email):
    with _real_client(db) as client:
        client.post("/auth/signup", json=SIGNUP_BODY)
        r = client.post("/auth/login", json={
            "email": SIGNUP_BODY["email"],
            "password": SIGNUP_BODY["password"],
        })
    assert r.status_code == 200
    assert r.json()["user"]["email_verified"] is False


# 16. Tests never hit SendGrid (FakeEmailService is used in all tests above)
def test_fake_email_service_used_not_sendgrid(db: Session, starter_plan, fake_email):
    """Verify that FakeEmailService is active — no real HTTP calls to SendGrid."""
    from app.services.email_service import get_email_service, FakeEmailService
    svc = get_email_service()
    assert isinstance(svc, FakeEmailService), "Real SendGrid must not be used in tests"
