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
from app.config import settings
from app.database import Base, get_db
from app.enums import MemberRole, MemberStatus, WorkspaceStatus
from app.main import app
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.plan import Plan
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription

TEST_DATABASE_URL = settings.database_test_url or settings.database_url.replace(
    "/nexbrain", "/nexbrain_test"
)

test_engine = create_engine(TEST_DATABASE_URL, echo=False)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)


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
    u = User(external_id=f"clerk_{uuid.uuid4().hex}", email=email, name=name)
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


# ── Common fixtures ────────────────────────────────────────────────────────────

@pytest.fixture()
def ai_model(db: Session) -> AiModel:
    return _make_ai_model(db)


@pytest.fixture()
def plan(db: Session) -> Plan:
    p = Plan(
        code="starter_test",
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
def subscription_a(db: Session, workspace_a: Workspace, plan: Plan) -> WorkspaceSubscription:
    return _make_subscription(db, workspace_a, plan)


# ── Client factory ─────────────────────────────────────────────────────────────

@contextmanager
def _make_client(
    db: Session, user: User, workspace: Workspace
) -> Generator[TestClient, None, None]:
    """
    Context manager that yields a TestClient with auth and workspace dependencies overridden.
    Always clears overrides on exit to prevent state leakage between tests.
    """
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def client_a(
    db: Session, user_a: User, workspace_a: Workspace
) -> Generator[TestClient, None, None]:
    with _make_client(db, user_a, workspace_a) as client:
        yield client


@pytest.fixture()
def client_b(
    db: Session, user_b: User, workspace_b: Workspace
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
    TestClient for public endpoints (no Clerk auth).
    Overrides only get_db so that the test database is used.
    Does NOT set get_current_user or get_current_workspace.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()
