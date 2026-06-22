"""
Auto-provisioning for first-time Nexbrain users.

When a Clerk-authenticated user makes their first request and does not yet exist
in the Nexbrain database, this service creates the full onboarding stack atomically:
  1. Fetches user profile from the Clerk API (before any DB writes).
  2. Creates the User record.
  3. Creates a default Workspace (owned by the user).
  4. Creates a WorkspaceMember entry (role: owner, status: active).
  5. Assigns the Starter plan with an active subscription (1-year period).
  6. Creates an initial UsageCounter for the current 30-day period.

All DB writes happen inside a single transaction. If anything fails before
db.commit(), the transaction is rolled back automatically when the session closes.

Idempotency: a race condition where two concurrent requests attempt to provision
the same user is handled via IntegrityError catch + re-lookup.
"""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import MemberRole, MemberStatus, WorkspaceStatus
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription

logger = logging.getLogger(__name__)


def _fetch_clerk_user(external_id: str) -> dict:
    """
    Fetch user profile from the Clerk REST API.
    Called BEFORE any DB writes so that a failure here leaves the DB untouched.
    """
    url = f"https://api.clerk.com/v1/users/{external_id}"
    headers = {"Authorization": f"Bearer {settings.clerk_secret_key}"}
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Clerk API returned %s for user %s", exc.response.status_code, external_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to fetch user profile from Clerk.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Clerk API request failed for user %s: %s", external_id, type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach Clerk API.",
        ) from exc


def _extract_profile(profile: dict) -> tuple[str, str, str | None]:
    """
    Extract (email, name, avatar_url) from a Clerk user profile dict.
    Prefers the primary email address when multiple are present.
    """
    emails = profile.get("email_addresses", [])
    if not emails:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Clerk user has no email address.",
        )

    primary_id = profile.get("primary_email_address_id")
    primary = next((e for e in emails if e.get("id") == primary_id), emails[0])
    email: str = primary["email_address"]

    first = (profile.get("first_name") or "").strip()
    last = (profile.get("last_name") or "").strip()
    name = f"{first} {last}".strip() or email.split("@")[0]

    avatar_url: str | None = profile.get("image_url") or None

    return email, name, avatar_url


def _unique_slug(base_email: str, db: Session) -> str:
    """
    Derive a workspace slug from the email prefix that is unique in the DB.
    Uses a sequential suffix on collision: lucas, lucas-1, lucas-2, …
    """
    base = re.sub(r"[^a-z0-9]", "-", base_email.split("@")[0].lower()).strip("-") or "workspace"
    base = base[:40]
    slug, suffix = base, 1
    while db.scalar(select(Workspace).where(Workspace.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _require_starter_plan(db: Session) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.code == "starter", Plan.is_active.is_(True)))
    if plan is None:
        logger.error("Starter plan not found in database — cannot provision new user.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform configuration error: starter plan not available.",
        )
    return plan


def provision_user(external_id: str, db: Session) -> User:
    """
    Provision a new Nexbrain user from their Clerk identity.

    Idempotent: returns the existing user immediately if already in the DB.
    Race-condition safe: catches IntegrityError on duplicate external_id and
    re-fetches the user that was committed by the concurrent request.

    The Clerk API is called BEFORE any DB writes so a network failure leaves
    the database clean.
    """
    # Fast path: user already exists (normal case after first provisioning)
    existing = db.scalar(select(User).where(User.external_id == external_id))
    if existing is not None:
        return existing

    # ── Fetch profile from Clerk (before any DB mutation) ────────────────────
    profile = _fetch_clerk_user(external_id)
    email, name, avatar_url = _extract_profile(profile)
    first_name = (profile.get("first_name") or "").strip()

    # ── Require Starter plan (fail early, before DB writes) ──────────────────
    starter = _require_starter_plan(db)

    # ── Build the full onboarding stack ──────────────────────────────────────
    user = User(
        id=uuid.uuid4(),
        external_id=external_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )
    db.add(user)
    db.flush()  # generate user.id for FK references below

    slug = _unique_slug(email, db)
    workspace_name = f"Workspace de {first_name}" if first_name else f"Workspace de {name}"
    workspace = Workspace(
        id=uuid.uuid4(),
        name=workspace_name,
        slug=slug,
        owner_user_id=user.id,
        status=WorkspaceStatus.active.value,
    )
    db.add(workspace)
    db.flush()  # generate workspace.id for FK references below

    db.add(WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=MemberRole.owner.value,
        status=MemberStatus.active.value,
    ))

    now = datetime.now(timezone.utc)
    db.add(WorkspaceSubscription(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        plan_id=starter.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=365),
    ))

    db.add(UsageCounter(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        period_start=now,
        period_end=now + timedelta(days=30),
    ))

    try:
        db.commit()
    except IntegrityError:
        # Another concurrent request already provisioned this user.
        db.rollback()
        user = db.scalar(select(User).where(User.external_id == external_id))
        if user is None:
            raise  # Integrity violation from something else — re-raise
        return user

    db.refresh(user)
    logger.info("Provisioned new user %s (workspace: %s)", user.id, workspace.slug)
    return user
