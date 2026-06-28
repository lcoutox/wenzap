"""
Tests for the auto-provisioning flow (provision_service.py).

Strategy:
- Tests that exercise the HTTP layer create a session cookie via _make_auth_session
  and use _make_cookie_client to call real endpoints.
- Tests for provision_user() directly call the function with the DB session
  and a mocked _fetch_clerk_user.

All tests assert on the actual database state to guarantee atomicity.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.provision_service import provision_user
from tests.conftest import _make_auth_session, _make_cookie_client

# ── Test data ─────────────────────────────────────────────────────────────────

EXTERNAL_ID = "clerk_test_provision_001"

FAKE_PROFILE = {
    "primary_email_address_id": "email_1",
    "email_addresses": [{"id": "email_1", "email_address": "newuser@example.com"}],
    "first_name": "New",
    "last_name": "User",
    "image_url": "https://example.com/avatar.jpg",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_starter(db: Session) -> Plan:
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
        monthly_ai_credits=500,
        monthly_conversations=200,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def _get_user(db: Session, external_id: str) -> User | None:
    return db.scalar(select(User).where(User.external_id == external_id))


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_first_login_creates_user(db: Session):
    """First login provisions a User record with correct fields."""
    _seed_starter(db)
    with patch(
        "app.services.provision_service._fetch_clerk_user", return_value=FAKE_PROFILE
    ):
        provision_user(EXTERNAL_ID, db)

    user = _get_user(db, EXTERNAL_ID)
    assert user is not None
    assert user.external_id == EXTERNAL_ID
    assert user.email == "newuser@example.com"
    assert user.name == "New User"
    assert user.avatar_url == "https://example.com/avatar.jpg"


def test_first_login_creates_workspace_member_and_subscription(db: Session):
    """First login creates Workspace + owner membership + active Starter subscription."""
    _seed_starter(db)
    with patch(
        "app.services.provision_service._fetch_clerk_user", return_value=FAKE_PROFILE
    ):
        user = provision_user(EXTERNAL_ID, db)

    # Workspace
    workspace = db.scalar(select(Workspace).where(Workspace.owner_user_id == user.id))
    assert workspace is not None
    assert workspace.status == "active"
    assert workspace.slug  # non-empty

    # WorkspaceMember — owner, active
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user.id,
        )
    )
    assert member is not None
    assert member.role == "owner"
    assert member.status == "active"

    # WorkspaceSubscription — Starter, active
    sub = db.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace.id
        )
    )
    assert sub is not None
    assert sub.status == "active"
    plan = db.scalar(select(Plan).where(Plan.id == sub.plan_id))
    assert plan is not None
    assert plan.code == "starter"


def test_first_login_creates_usage_counter(db: Session):
    """First login creates an initial UsageCounter for the current period."""
    _seed_starter(db)
    with patch(
        "app.services.provision_service._fetch_clerk_user", return_value=FAKE_PROFILE
    ):
        user = provision_user(EXTERNAL_ID, db)

    workspace = db.scalar(select(Workspace).where(Workspace.owner_user_id == user.id))
    assert workspace is not None

    counter = db.scalar(
        select(UsageCounter).where(UsageCounter.workspace_id == workspace.id)
    )
    assert counter is not None
    assert counter.ai_credits_used == 0
    assert counter.conversations_count == 0
    assert counter.period_end > counter.period_start


def test_second_login_does_not_duplicate(db: Session):
    """Calling provision_user twice for the same external_id returns the same user."""
    _seed_starter(db)
    with patch(
        "app.services.provision_service._fetch_clerk_user", return_value=FAKE_PROFILE
    ):
        user1 = provision_user(EXTERNAL_ID, db)
        user2 = provision_user(EXTERNAL_ID, db)

    assert user1.id == user2.id

    # Exactly one user, one workspace, one member, one subscription
    users = db.scalars(select(User).where(User.external_id == EXTERNAL_ID)).all()
    assert len(users) == 1

    workspaces = db.scalars(
        select(Workspace).where(Workspace.owner_user_id == user1.id)
    ).all()
    assert len(workspaces) == 1

    members = db.scalars(
        select(WorkspaceMember).where(WorkspaceMember.user_id == user1.id)
    ).all()
    assert len(members) == 1

    subs = db.scalars(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspaces[0].id
        )
    ).all()
    assert len(subs) == 1


def test_provisioned_user_can_call_me(db: Session):
    """After provisioning (via provision_user), GET /me works with a real cookie session."""
    _seed_starter(db)
    with patch(
        "app.services.provision_service._fetch_clerk_user", return_value=FAKE_PROFILE
    ):
        user = provision_user(EXTERNAL_ID, db)

    workspace = db.scalar(select(Workspace).where(Workspace.owner_user_id == user.id))
    assert workspace is not None

    token = _make_auth_session(db, user)
    with _make_cookie_client(db, token) as client:
        response = client.get("/me")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "newuser@example.com"
    assert body["name"] == "New User"
    assert body["role"] == "owner"
    assert body["workspace"]["status"] == "active"


def test_no_starter_plan_returns_503(db: Session):
    """provision_user raises HTTP 503 when the Starter plan does not exist in DB."""
    # No plan seeded
    with patch(
        "app.services.provision_service._fetch_clerk_user", return_value=FAKE_PROFILE
    ):
        with pytest.raises(Exception) as exc_info:
            provision_user(EXTERNAL_ID, db)

    from fastapi import HTTPException
    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 503

    # No partial data left
    assert _get_user(db, EXTERNAL_ID) is None


def test_existing_user_is_not_reprovisioned(db: Session):
    """A user that already exists in DB is returned directly without calling Clerk API."""
    _seed_starter(db)
    # Create a user with a real external_id (as would exist from a prior Clerk provision)
    existing = User(external_id=EXTERNAL_ID, email="existing@example.com", name="Existing User")
    db.add(existing)
    db.commit()
    db.refresh(existing)

    fetch_mock = patch("app.services.provision_service._fetch_clerk_user")
    with fetch_mock as mock_fetch:
        result = provision_user(EXTERNAL_ID, db)

    mock_fetch.assert_not_called()
    assert result.id == existing.id


def test_primary_email_is_used_when_multiple_present(db: Session):
    """When the profile has multiple emails, the primary one is used."""
    _seed_starter(db)
    profile_multi_email = {
        "primary_email_address_id": "email_primary",
        "email_addresses": [
            {"id": "email_other", "email_address": "other@example.com"},
            {"id": "email_primary", "email_address": "primary@example.com"},
        ],
        "first_name": "Multi",
        "last_name": "Email",
        "image_url": None,
    }
    with patch(
        "app.services.provision_service._fetch_clerk_user", return_value=profile_multi_email
    ):
        user = provision_user(EXTERNAL_ID, db)

    assert user.email == "primary@example.com"
