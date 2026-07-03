"""
Test fixtures.

Uses a real PostgreSQL test database (postgres_test on port 5433).
Each test cleans all tables via the `db` fixture teardown.

Dependency overrides are always cleared after each test that uses a client fixture,
preventing state leakage between tests.
"""

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.auth.sessions import create_session
from app.config import settings
from app.database import Base, get_db
from app.enums import MemberRole, MemberStatus, WorkspaceStatus
from app.main import app
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.plan import Plan
from app.models.plan_feature import PlanFeature
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.rate_limiter import _store as _rate_limiter_store

TEST_DATABASE_URL = settings.database_test_url or settings.database_url.replace(
    "/nexbrain", "/nexbrain_test"
)

test_engine = create_engine(TEST_DATABASE_URL, echo=False)


def _reset_schema(engine) -> None:
    """Drop and recreate the public schema to avoid FK circular-dependency issues."""
    from sqlalchemy import text  # noqa: PLC0415

    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    _reset_schema(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    _reset_schema(test_engine)


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    """Reset the in-memory rate limiter between every test to prevent cross-test leakage."""
    _rate_limiter_store.clear()
    yield
    _rate_limiter_store.clear()


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    with Session(test_engine) as session:
        yield session
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


# ── Factories ─────────────────────────────────────────────────────────────────

def _make_user(db: Session, email: str, name: str) -> User:
    from datetime import datetime, timezone  # noqa: PLC0415
    u = User(external_id=None, email=email, name=name, email_verified=True,
             email_verified_at=datetime.now(timezone.utc))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_workspace(db: Session, owner: User, slug: str, name: str) -> Workspace:
    w = Workspace(name=name, slug=slug, owner_user_id=owner.id, status=WorkspaceStatus.active)
    db.add(w)
    db.commit()
    db.refresh(w)
    m = WorkspaceMember(
        workspace_id=w.id, user_id=owner.id, role=MemberRole.owner, status=MemberStatus.active
    )
    db.add(m)
    db.commit()
    return w


def _make_ai_model(
    db: Session,
    *,
    code: str | None = None,
    min_plan_code: str = "starter",
    is_default: bool = True,
) -> AiModel:
    """Create a minimal AiModelProvider + AiModel for use in tests."""
    uid = uuid.uuid4().hex[:8]
    provider = AiModelProvider(
        id=uuid.uuid4(),
        code=code or f"test-provider-{uid}",
        name="Test Provider",
        is_active=True,
    )
    db.add(provider)
    db.flush()
    model = AiModel(
        id=uuid.uuid4(),
        provider_id=provider.id,
        code=code or f"test-model-{uid}",
        display_name="Test Model",
        model_name=f"test-model-{uid}-v1",
        credits_per_message=1,
        min_plan_code=min_plan_code,
        is_default=is_default,
        is_active=True,
        sort_order=1,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


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
    db.commit()
    db.refresh(sub)
    return sub


def _make_auth_session(db: Session, user: User) -> str:
    """Create a real auth session for user and return the raw session token."""
    _, token = create_session(db, user.id)
    db.commit()
    return token


# ── Feature-gate seed ─────────────────────────────────────────────────────────

_FEATURE_MATRIX = [
    # starter
    ("starter", "web_widget",               True),
    ("starter", "api",                      True),
    ("starter", "knowledge_base",           True),
    ("starter", "inbox",                    True),
    ("starter", "playground",               True),
    ("starter", "whatsapp",                 False),
    ("starter", "instagram",                False),
    ("starter", "telegram",                 False),
    ("starter", "slack",                    False),
    ("starter", "catalog",                  True),   # starter: catalog enabled (limited qty)
    ("starter", "pipelines",                True),
    ("starter", "pipeline_automations",     False),
    ("starter", "multiple_knowledge_bases", False),
    ("starter", "whatsapp_channel",         False),
    ("starter", "api_access",               False),
    ("starter", "http_tools",               False),
    ("starter", "follow_up",                False),
    ("starter", "webhooks",                 False),
    ("starter", "custom_model",             False),
    ("starter", "analytics",                False),
    ("starter", "external_integrations",    False),
    ("starter", "remove_powered_by",        False),
    ("starter", "premium_models",           False),
    # growth
    ("growth",  "web_widget",               True),
    ("growth",  "api",                      True),
    ("growth",  "knowledge_base",           True),
    ("growth",  "inbox",                    True),
    ("growth",  "playground",               True),
    ("growth",  "whatsapp",                 True),
    ("growth",  "catalog",                  True),
    ("growth",  "pipelines",                True),
    ("growth",  "pipeline_automations",     False),
    ("growth",  "multiple_knowledge_bases", True),
    ("growth",  "whatsapp_channel",         True),
    ("growth",  "api_access",               True),
    ("growth",  "instagram",                False),
    ("growth",  "telegram",                 False),
    ("growth",  "slack",                    False),
    ("growth",  "http_tools",               False),
    ("growth",  "follow_up",                False),
    ("growth",  "webhooks",                 False),
    ("growth",  "custom_model",             False),
    ("growth",  "analytics",                False),
    ("growth",  "external_integrations",    False),
    ("growth",  "remove_powered_by",        False),
    ("growth",  "premium_models",           False),
    # scale
    ("scale",   "web_widget",               True),
    ("scale",   "api",                      True),
    ("scale",   "knowledge_base",           True),
    ("scale",   "inbox",                    True),
    ("scale",   "playground",               True),
    ("scale",   "whatsapp",                 True),
    ("scale",   "instagram",                True),
    ("scale",   "telegram",                 True),
    ("scale",   "catalog",                  True),
    ("scale",   "pipelines",                True),
    ("scale",   "pipeline_automations",     True),
    ("scale",   "multiple_knowledge_bases", True),
    ("scale",   "whatsapp_channel",         True),
    ("scale",   "api_access",               True),
    ("scale",   "http_tools",               True),
    ("scale",   "follow_up",                True),
    ("scale",   "webhooks",                 True),
    ("scale",   "custom_model",             True),
    ("scale",   "analytics",                True),
    ("scale",   "external_integrations",    True),
    ("scale",   "remove_powered_by",        False),  # Enterprise-only
    ("scale",   "premium_models",           True),
    ("scale",   "slack",                    False),
    # enterprise
    ("enterprise", "web_widget",               True),
    ("enterprise", "api",                      True),
    ("enterprise", "knowledge_base",           True),
    ("enterprise", "inbox",                    True),
    ("enterprise", "playground",               True),
    ("enterprise", "whatsapp",                 True),
    ("enterprise", "instagram",                True),
    ("enterprise", "telegram",                 True),
    ("enterprise", "slack",                    True),
    ("enterprise", "catalog",                  True),
    ("enterprise", "pipelines",                True),
    ("enterprise", "pipeline_automations",     True),
    ("enterprise", "multiple_knowledge_bases", True),
    ("enterprise", "whatsapp_channel",         True),
    ("enterprise", "api_access",               True),
    ("enterprise", "http_tools",               True),
    ("enterprise", "follow_up",                True),
    ("enterprise", "webhooks",                 True),
    ("enterprise", "custom_model",             True),
    ("enterprise", "analytics",                True),
    ("enterprise", "external_integrations",    True),
    ("enterprise", "remove_powered_by",        True),
    ("enterprise", "premium_models",           True),
]


_SEED_PLANS = [
    ("starter",    "Free",       True,  10),
    ("growth",     "Growth",     True,  20),
    ("scale",      "Scale",      False, 30),
    ("enterprise", "Enterprise", False, 40),
]


def _seed_feature_matrix(db: Session) -> None:
    """Populate plan_features with the standard feature matrix.

    Creates minimal plan rows for starter/growth/scale/enterprise if they don't
    exist yet (required by the FK plan_code → plans.code). Uses get-or-create so
    this is safe regardless of whether the `plan` fixture has already run.
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    from sqlalchemy import select as _select  # noqa: PLC0415

    now = datetime.now(timezone.utc)

    for code, name, is_public, sort_order in _SEED_PLANS:
        if not db.scalar(_select(Plan).where(Plan.code == code)):
            db.add(Plan(code=code, name=name, is_public=is_public, sort_order=sort_order))
    db.flush()

    for plan_code, feature_key, enabled in _FEATURE_MATRIX:
        db.add(
            PlanFeature(
                plan_code=plan_code,
                feature_key=feature_key,
                enabled=enabled,
                created_at=now,
            )
        )
    db.commit()


@pytest.fixture()
def feature_matrix(db: Session) -> None:
    """Seed the plan_features table for tests that call plan_allows_feature / plan_allows_channel_type."""
    _seed_feature_matrix(db)


# ── Common fixtures ────────────────────────────────────────────────────────────

@pytest.fixture()
def ai_model(db: Session) -> AiModel:
    return _make_ai_model(db)


@pytest.fixture()
def plan(db: Session) -> Plan:
    from sqlalchemy import select as _sel  # noqa: PLC0415

    p = db.scalar(_sel(Plan).where(Plan.code == "starter"))
    if p is None:
        p = Plan(
            code="starter",
            name="Starter Test",
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
            is_public=True,
            sort_order=10,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


@pytest.fixture()
def user_a(db: Session) -> User:
    return _make_user(db, "user_a@test.com", "User A")


@pytest.fixture()
def user_b(db: Session) -> User:
    return _make_user(db, "user_b@test.com", "User B")


@pytest.fixture()
def workspace_a(db: Session, user_a: User) -> Workspace:
    return _make_workspace(db, user_a, "workspace-a", "Workspace A")


@pytest.fixture()
def workspace_b(db: Session, user_b: User) -> Workspace:
    return _make_workspace(db, user_b, "workspace-b", "Workspace B")


@pytest.fixture()
def growth_plan(db: Session) -> Plan:
    """Growth plan for tests that need WhatsApp or other growth+ features."""
    from sqlalchemy import select as _sel  # noqa: PLC0415

    p = db.scalar(_sel(Plan).where(Plan.code == "growth"))
    if p is None:
        p = Plan(
            code="growth",
            name="Growth Test",
            monthly_price_cents=29700,
            currency="BRL",
            agents_limit=3,
            knowledge_bases_limit=5,
            users_limit=5,
            pipelines_limit=5,
            integrations_limit=5,
            monthly_ai_credits=7500,
            monthly_conversations=0,
            is_active=True,
            is_public=True,
            sort_order=20,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


@pytest.fixture()
def subscription_a(db: Session, workspace_a: Workspace, plan: Plan, feature_matrix) -> WorkspaceSubscription:
    return _make_subscription(db, workspace_a, plan)


@pytest.fixture()
def subscription_b(db: Session, workspace_b: Workspace, plan: Plan, feature_matrix) -> WorkspaceSubscription:
    return _make_subscription(db, workspace_b, plan)


@pytest.fixture()
def growth_subscription_a(
    db: Session, workspace_a: Workspace, subscription_a: WorkspaceSubscription, growth_plan: Plan, feature_matrix
) -> WorkspaceSubscription:
    """Upgrade workspace_a's existing subscription to the Growth plan."""
    from sqlalchemy import update as _update  # noqa: PLC0415

    db.execute(
        _update(WorkspaceSubscription)
        .where(WorkspaceSubscription.workspace_id == workspace_a.id)
        .values(plan_id=growth_plan.id, status="active")
    )
    db.commit()
    db.refresh(subscription_a)
    return subscription_a


@pytest.fixture()
def growth_subscription_b(
    db: Session, workspace_b: Workspace, subscription_b: WorkspaceSubscription, growth_plan: Plan, feature_matrix
) -> WorkspaceSubscription:
    """Upgrade workspace_b's existing subscription to the Growth plan."""
    from sqlalchemy import update as _update  # noqa: PLC0415

    db.execute(
        _update(WorkspaceSubscription)
        .where(WorkspaceSubscription.workspace_id == workspace_b.id)
        .values(plan_id=growth_plan.id, status="active")
    )
    db.commit()
    db.refresh(subscription_b)
    return subscription_b


# ── Client factories ──────────────────────────────────────────────────────────

@contextmanager
def _make_client(
    db: Session, user: User, workspace: Workspace
) -> Generator[TestClient, None, None]:
    """
    Context manager that yields a TestClient with auth and workspace dependencies overridden.
    Used by most existing tests that don't need to exercise the real auth stack.
    Always clears overrides on exit to prevent state leakage between tests.
    """
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()


@contextmanager
def _make_cookie_client(db: Session, token: str) -> Generator[TestClient, None, None]:
    """
    Context manager that yields a TestClient authenticated via the real cookie-based
    auth stack (no dependency overrides). Use this to test the full auth path.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app, raise_server_exceptions=True)
        client.cookies.set(settings.auth_cookie_name, token)
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client_a(
    db: Session, user_a: User, workspace_a: Workspace, subscription_a: WorkspaceSubscription
) -> Generator[TestClient, None, None]:
    with _make_client(db, user_a, workspace_a) as client:
        yield client


@pytest.fixture()
def client_b(
    db: Session, user_b: User, workspace_b: Workspace, subscription_b: WorkspaceSubscription
) -> Generator[TestClient, None, None]:
    with _make_client(db, user_b, workspace_b) as client:
        yield client


@pytest.fixture()
def unauthenticated_client() -> Generator[TestClient, None, None]:
    app.dependency_overrides.clear()
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def public_client(db: Session) -> Generator[TestClient, None, None]:
    """
    TestClient for public endpoints (no auth).
    Overrides only get_db so that the test database is used.
    Does NOT set get_current_user or get_current_workspace.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()
