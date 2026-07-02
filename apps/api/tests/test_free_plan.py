"""
Tests for Billing/Plans.1 & Plans.3 — Free Plan Matrix, Feature Gates & Limit Enforcement.

Covers:
  - Feature gate: WhatsApp channel blocked on Free plan (HTTP 402)
  - Feature gate: Web widget allowed on Free plan
  - Feature gate: plan_allows_channel_type helper
  - Feature gate: plan_allows_feature helper (remove_powered_by, pipelines)
  - Usage counter: get_or_create_usage_counter creates on-demand
  - Usage counter: get_or_create_usage_counter returns existing row
  - Conversations: count_new_conversation increments counter (Plans.3: no blocking)
  - Conversations: counter increments even when conversations_count > monthly_conversations
  - Conversations: conversations_count=0 means unlimited is no longer relevant (never blocked)
  - Users limit: check_users_limit raises 402 at limit
  - Users limit: check_users_limit allows below limit
  - Plan service: get_or_create_usage_counter idempotent (two calls same counter)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus, WorkspaceStatus
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.plan_feature_service import (
    check_channel_type_or_402,
    check_users_limit,
    plan_allows_channel_type,
    plan_allows_feature,
)
from app.services.plan_service import (
    count_new_conversation,
    get_or_create_usage_counter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(
    db: Session,
    *,
    code: str = "free_test",
    monthly_conversations: int = 50,
    monthly_ai_credits: int = 200,
    knowledge_bases_limit: int = 1,
    users_limit: int = 1,
    channels_limit: int = 1,
) -> Plan:
    plan = Plan(
        code=code,
        name="Free Test",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=1,
        knowledge_bases_limit=knowledge_bases_limit,
        users_limit=users_limit,
        pipelines_limit=0,
        integrations_limit=0,
        channels_limit=channels_limit,
        monthly_ai_credits=monthly_ai_credits,
        monthly_conversations=monthly_conversations,
        is_active=True,
    )
    db.add(plan)
    db.flush()
    return plan


def _make_user(db: Session) -> User:
    u = User(external_id=None, email=f"{uuid.uuid4().hex[:8]}@test.com", name="Test User")
    db.add(u)
    db.flush()
    return u


def _make_workspace(db: Session) -> Workspace:
    owner = _make_user(db)
    ws = Workspace(
        slug=f"ws-{uuid.uuid4().hex[:8]}",
        name="Test WS",
        owner_user_id=owner.id,
        status=WorkspaceStatus.active,
    )
    db.add(ws)
    db.flush()
    member = WorkspaceMember(
        workspace_id=ws.id,
        user_id=owner.id,
        role=MemberRole.owner,
        status=MemberStatus.active,
    )
    db.add(member)
    db.flush()
    return ws


def _make_subscription(db: Session, workspace: Workspace, plan: Plan) -> WorkspaceSubscription:
    now = datetime.now(timezone.utc)
    sub = WorkspaceSubscription(
        workspace_id=workspace.id,
        plan_id=plan.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    db.flush()
    return sub


def _make_counter(
    db: Session,
    workspace: Workspace,
    *,
    conversations_count: int = 0,
    ai_credits_used: int = 0,
) -> UsageCounter:
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        next_month = period_start.replace(year=period_start.year + 1, month=1, day=1)
    else:
        next_month = period_start.replace(month=period_start.month + 1, day=1)
    period_end = next_month - timedelta(seconds=1)
    counter = UsageCounter(
        workspace_id=workspace.id,
        period_start=period_start,
        period_end=period_end,
        ai_credits_used=ai_credits_used,
        conversations_count=conversations_count,
        messages_count=0,
    )
    db.add(counter)
    db.flush()
    return counter


# ---------------------------------------------------------------------------
# Feature gate: channel types
# ---------------------------------------------------------------------------

def test_plan_allows_web_widget_on_free(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "starter", "web_widget") is True


def test_plan_allows_api_on_free(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "starter", "api") is True


def test_plan_blocks_whatsapp_on_free(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "starter", "whatsapp") is False


def test_plan_allows_whatsapp_on_growth(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "growth", "whatsapp") is True


def test_plan_blocks_instagram_on_growth(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "growth", "instagram") is False


def test_plan_allows_instagram_on_scale(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "scale", "instagram") is True


# ---------------------------------------------------------------------------
# Feature gate: features
# ---------------------------------------------------------------------------

def test_free_plan_cannot_remove_powered_by(db: Session, feature_matrix):
    assert plan_allows_feature(db, "starter", "remove_powered_by") is False


def test_growth_plan_cannot_remove_powered_by(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "remove_powered_by") is False


def test_scale_plan_cannot_remove_powered_by(db: Session, feature_matrix):
    # remove_powered_by is Enterprise-only
    assert plan_allows_feature(db, "scale", "remove_powered_by") is False


def test_enterprise_plan_can_remove_powered_by(db: Session, feature_matrix):
    assert plan_allows_feature(db, "enterprise", "remove_powered_by") is True


def test_free_plan_can_use_catalog(db: Session, feature_matrix):
    # Catalog is available on starter so users can test a core feature
    assert plan_allows_feature(db, "starter", "catalog") is True


def test_free_plan_can_use_pipelines(db: Session, feature_matrix):
    # Pipeline.1: starter plan now includes pipelines (updated from False → True)
    assert plan_allows_feature(db, "starter", "pipelines") is True


def test_growth_plan_can_use_pipelines(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "pipelines") is True


def test_unknown_feature_default_deny(db: Session, feature_matrix):
    # Default deny: absent feature_key → False
    assert plan_allows_feature(db, "starter", "nonexistent_feature") is False


# ---------------------------------------------------------------------------
# check_channel_type_or_402
# ---------------------------------------------------------------------------

def _get_or_make_starter_plan(db: Session) -> Plan:
    """Return the seeded 'starter' plan or create a test one if not seeded."""
    from sqlalchemy import select as _select  # noqa: PLC0415

    plan = db.scalar(_select(Plan).where(Plan.code == "starter"))
    if plan is None:
        plan = Plan(
            code="starter",
            name="Free",
            monthly_price_cents=0,
            currency="BRL",
            agents_limit=1,
            knowledge_bases_limit=1,
            users_limit=1,
            pipelines_limit=0,
            integrations_limit=0,
            channels_limit=1,
            monthly_ai_credits=200,
            monthly_conversations=50,
            is_active=True,
        )
        db.add(plan)
        db.flush()
    return plan


def test_whatsapp_blocked_for_free_plan(db: Session, feature_matrix):
    plan = _get_or_make_starter_plan(db)
    ws = _make_workspace(db)
    _make_subscription(db, ws, plan)
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        check_channel_type_or_402(db, ws.id, "whatsapp")

    assert exc_info.value.status_code == 402
    assert "whatsapp" in exc_info.value.detail.lower()


def test_web_widget_allowed_for_free_plan(db: Session, feature_matrix):
    plan = _get_or_make_starter_plan(db)
    ws = _make_workspace(db)
    _make_subscription(db, ws, plan)
    db.commit()

    # Should not raise
    check_channel_type_or_402(db, ws.id, "web_widget")


# ---------------------------------------------------------------------------
# get_or_create_usage_counter
# ---------------------------------------------------------------------------

def test_get_or_create_creates_counter_when_missing(db: Session):
    ws = _make_workspace(db)
    db.commit()

    counter = get_or_create_usage_counter(db, ws.id)

    assert counter is not None
    assert counter.workspace_id == ws.id
    assert counter.conversations_count == 0
    assert counter.ai_credits_used == 0


def test_get_or_create_returns_existing_counter(db: Session):
    ws = _make_workspace(db)
    existing = _make_counter(db, ws, conversations_count=5)
    db.commit()

    counter = get_or_create_usage_counter(db, ws.id)

    assert counter.id == existing.id
    assert counter.conversations_count == 5


def test_get_or_create_is_idempotent(db: Session):
    ws = _make_workspace(db)
    db.commit()

    c1 = get_or_create_usage_counter(db, ws.id)
    db.commit()
    c2 = get_or_create_usage_counter(db, ws.id)

    assert c1.id == c2.id


# ---------------------------------------------------------------------------
# count_new_conversation (Plans.3: metric only, never blocks)
# ---------------------------------------------------------------------------

def test_conversation_increments_counter(db: Session):
    """count_new_conversation increments conversations_count."""
    ws = _make_workspace(db)
    _make_counter(db, ws, conversations_count=0)
    db.commit()

    count_new_conversation(db, ws.id)
    db.commit()

    counter = get_or_create_usage_counter(db, ws.id)
    assert counter.conversations_count == 1


def test_conversation_never_blocks_even_at_limit(db: Session):
    """Conversations exceeding monthly_conversations must not raise HTTP 402."""
    plan = _make_plan(db, code=f"starter_{uuid.uuid4().hex[:6]}", monthly_conversations=2)
    ws = _make_workspace(db)
    _make_subscription(db, ws, plan)
    _make_counter(db, ws, conversations_count=2)
    db.commit()

    # Must not raise — conversations are a metric, not a hard gate
    count_new_conversation(db, ws.id)
    db.commit()

    counter = get_or_create_usage_counter(db, ws.id)
    assert counter.conversations_count == 3


def test_conversation_increments_well_above_limit(db: Session):
    """Counter can exceed monthly_conversations without any error."""
    plan = _make_plan(db, code=f"starter_{uuid.uuid4().hex[:6]}", monthly_conversations=1)
    ws = _make_workspace(db)
    _make_subscription(db, ws, plan)
    _make_counter(db, ws, conversations_count=9999)
    db.commit()

    count_new_conversation(db, ws.id)
    db.commit()

    counter = get_or_create_usage_counter(db, ws.id)
    assert counter.conversations_count == 10000


# ---------------------------------------------------------------------------
# check_users_limit
# ---------------------------------------------------------------------------

def test_users_limit_allows_below_limit(db: Session):
    plan = _make_plan(db, code=f"starter_{uuid.uuid4().hex[:6]}", users_limit=3)
    ws = _make_workspace(db)
    _make_subscription(db, ws, plan)
    db.commit()

    # Should not raise (0 active members < 3 limit)
    check_users_limit(db, ws.id)


def test_users_limit_blocked_at_limit(db: Session):
    plan = _make_plan(db, code=f"starter_{uuid.uuid4().hex[:6]}", users_limit=1)
    ws = _make_workspace(db)
    _make_subscription(db, ws, plan)

    db.commit()
    # _make_workspace creates owner as an active member — with users_limit=1, already at limit.

    with pytest.raises(HTTPException) as exc_info:
        check_users_limit(db, ws.id)

    assert exc_info.value.status_code == 402
