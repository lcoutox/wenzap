"""
Tests for Knowledge Base CRUD — Phase 4.1.2.

Covers:
  1. CRUD (create, list, get, update, archive)
  2. Plan limits
  3. RBAC
  4. Tenant isolation
  5. Archive side-effects (agent connections)
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus, SubscriptionStatus
from app.models.agent import Agent
from app.models.agent_knowledge_base import AgentKnowledgeBase
from app.models.knowledge_base import KnowledgeBase
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_plan(
    db: Session,
    *,
    knowledge_bases_limit: int = 10,
    sources_per_kb_limit: int = 20,
    max_source_chars: int = 50000,
) -> Plan:
    p = Plan(
        code=f"test-plan-{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=knowledge_bases_limit,
        sources_per_kb_limit=sources_per_kb_limit,
        max_source_chars=max_source_chars,
        users_limit=10,
        pipelines_limit=1,
        integrations_limit=0,
        monthly_ai_credits=1000,
        monthly_conversations=500,
        is_active=True,
    )
    db.add(p)
    db.flush()
    return p


def _make_subscription(db: Session, workspace_id: uuid.UUID, plan: Plan) -> None:
    now = datetime.now(timezone.utc)
    sub = WorkspaceSubscription(
        workspace_id=workspace_id,
        plan_id=plan.id,
        status=SubscriptionStatus.active.value,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    db.flush()


def _make_member(
    db: Session,
    workspace_id: uuid.UUID,
    role: MemberRole,
    *,
    email_prefix: str | None = None,
) -> object:
    from app.models.workspace_member import WorkspaceMember

    email = f"{email_prefix or role.value}-{uuid.uuid4().hex[:6]}@test.com"
    user = _make_user(db, email, f"{role.value.title()} User")
    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role=role,
        status=MemberStatus.active,
    )
    db.add(member)
    db.flush()
    return user


def _make_kb(db: Session, workspace_id: uuid.UUID, *, name: str = "Test KB") -> KnowledgeBase:
    kb = KnowledgeBase(workspace_id=workspace_id, name=name, status="active")
    db.add(kb)
    db.flush()
    return kb


def _post_kb(client, *, name: str = "My KB", description: str | None = None) -> dict:
    body: dict = {"name": name}
    if description is not None:
        body["description"] = description
    return client.post("/knowledge-bases", json=body)


def _setup(db: Session, *, knowledge_bases_limit: int = 10):
    """Return (owner, workspace) with a subscription."""
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "Test WS")
    plan = _make_plan(db, knowledge_bases_limit=knowledge_bases_limit)
    _make_subscription(db, ws.id, plan)
    db.commit()
    return owner, ws


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CRUD
# ═══════════════════════════════════════════════════════════════════════════════

def test_create_kb_returns_201(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_kb(client, name="Support FAQ")
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Support FAQ"
    assert body["status"] == "active"
    assert body["workspace_id"] == str(ws.id)


def test_create_kb_with_description(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_kb(client, name="KB", description="Our support knowledge")
    assert r.status_code == 201
    assert r.json()["description"] == "Our support knowledge"


def test_create_kb_sets_created_by_user_id(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_kb(client)
    assert r.json()["created_by_user_id"] == str(owner.id)


def test_list_kbs_returns_own_workspace_only(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        _post_kb(client, name="KB 1")
        _post_kb(client, name="KB 2")
        r = client.get("/knowledge-bases")
    assert r.status_code == 200
    names = [kb["name"] for kb in r.json()]
    assert "KB 1" in names
    assert "KB 2" in names


def test_get_kb_returns_200(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client).json()["id"]
        r = client.get(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 200
    assert r.json()["id"] == kb_id


def test_update_name(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client, name="Old Name").json()["id"]
        r = client.patch(f"/knowledge-bases/{kb_id}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_description(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client).json()["id"]
        r = client.patch(f"/knowledge-bases/{kb_id}", json={"description": "Updated desc"})
    assert r.status_code == 200
    assert r.json()["description"] == "Updated desc"


def test_clear_description_with_null(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client, description="Initial desc").json()["id"]
        r = client.patch(f"/knowledge-bases/{kb_id}", json={"description": None})
    assert r.status_code == 200
    assert r.json()["description"] is None


def test_patch_without_fields_is_noop(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client, name="Stable").json()["id"]
        r = client.patch(f"/knowledge-bases/{kb_id}", json={})
    assert r.status_code == 200
    assert r.json()["name"] == "Stable"


def test_patch_name_null_returns_422(db):
    """name cannot be explicitly nulled — NOT NULL constraint in DB."""
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client, name="Protected").json()["id"]
        r = client.patch(f"/knowledge-bases/{kb_id}", json={"name": None})
    assert r.status_code == 422


def test_archive_kb_changes_status(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client).json()["id"]
        r = client.delete(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


def test_archived_kb_not_in_listing(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client, name="To Archive").json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}")
        r = client.get("/knowledge-bases")
    ids = [kb["id"] for kb in r.json()]
    assert kb_id not in ids


def test_get_archived_kb_returns_404(db):
    # Archived KBs are treated as not found to keep the main flow clean.
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client).json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}")
        r = client.get(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 404


def test_patch_archived_kb_returns_404(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client).json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}")
        r = client.patch(f"/knowledge-bases/{kb_id}", json={"name": "Ghost"})
    assert r.status_code == 404


def test_create_kb_empty_name_returns_422(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.post("/knowledge-bases", json={"name": ""})
    assert r.status_code == 422


def test_create_kb_missing_name_returns_422(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.post("/knowledge-bases", json={})
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Plan limits
# ═══════════════════════════════════════════════════════════════════════════════

def test_kb_limit_blocks_creation(db):
    owner, ws = _setup(db, knowledge_bases_limit=2)
    with _make_client(db, owner, ws) as client:
        _post_kb(client, name="KB 1")
        _post_kb(client, name="KB 2")
        r = _post_kb(client, name="KB 3")
    assert r.status_code == 402


def test_archived_kbs_do_not_count_toward_limit(db):
    owner, ws = _setup(db, knowledge_bases_limit=2)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client, name="KB 1").json()["id"]
        _post_kb(client, name="KB 2")
        # archive one to free up a slot
        client.delete(f"/knowledge-bases/{kb_id}")
        r = _post_kb(client, name="KB 3")
    assert r.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# 3. RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_viewer_can_list_kbs(db):
    owner, ws = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    with _make_client(db, owner, ws) as c_owner:
        _post_kb(c_owner)
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.get("/knowledge-bases")
    assert r.status_code == 200


def test_viewer_can_get_kb(db):
    owner, ws = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    with _make_client(db, owner, ws) as c_owner:
        kb_id = _post_kb(c_owner).json()["id"]
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.get(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 200


def test_viewer_cannot_create_kb(db):
    owner, ws = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    with _make_client(db, viewer, ws) as client:
        r = _post_kb(client)
    assert r.status_code == 403


def test_viewer_cannot_update_kb(db):
    owner, ws = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    with _make_client(db, owner, ws) as c_owner:
        kb_id = _post_kb(c_owner).json()["id"]
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.patch(f"/knowledge-bases/{kb_id}", json={"name": "Nope"})
    assert r.status_code == 403


def test_viewer_cannot_archive_kb(db):
    owner, ws = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    with _make_client(db, owner, ws) as c_owner:
        kb_id = _post_kb(c_owner).json()["id"]
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.delete(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 403


def test_member_can_create_kb(db):
    owner, ws = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    with _make_client(db, member, ws) as client:
        r = _post_kb(client)
    assert r.status_code == 201


def test_member_can_update_kb(db):
    owner, ws = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    with _make_client(db, owner, ws) as c_owner:
        kb_id = _post_kb(c_owner).json()["id"]
    with _make_client(db, member, ws) as c_member:
        r = c_member.patch(f"/knowledge-bases/{kb_id}", json={"name": "Member Edit"})
    assert r.status_code == 200


def test_member_cannot_archive_kb(db):
    owner, ws = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    with _make_client(db, owner, ws) as c_owner:
        kb_id = _post_kb(c_owner).json()["id"]
    with _make_client(db, member, ws) as c_member:
        r = c_member.delete(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 403


def test_admin_can_archive_kb(db):
    owner, ws = _setup(db)
    admin = _make_member(db, ws.id, MemberRole.admin)
    with _make_client(db, owner, ws) as c_owner:
        kb_id = _post_kb(c_owner).json()["id"]
    with _make_client(db, admin, ws) as c_admin:
        r = c_admin.delete(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 200


def test_owner_can_archive_kb(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = _post_kb(client).json()["id"]
        r = client.delete(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Tenant isolation
# ═══════════════════════════════════════════════════════════════════════════════

def test_list_does_not_return_other_workspace_kbs(db):
    owner_a, ws_a = _setup(db)
    owner_b, ws_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        kb_id = _post_kb(c_a, name="WS-A KB").json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.get("/knowledge-bases")
    ids = [kb["id"] for kb in r.json()]
    assert kb_id not in ids


def test_get_cross_workspace_kb_returns_404(db):
    owner_a, ws_a = _setup(db)
    owner_b, ws_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        kb_id = _post_kb(c_a).json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.get(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 404


def test_patch_cross_workspace_kb_returns_404(db):
    owner_a, ws_a = _setup(db)
    owner_b, ws_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        kb_id = _post_kb(c_a).json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.patch(f"/knowledge-bases/{kb_id}", json={"name": "Hijack"})
    assert r.status_code == 404


def test_delete_cross_workspace_kb_returns_404(db):
    owner_a, ws_a = _setup(db)
    owner_b, ws_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        kb_id = _post_kb(c_a).json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.delete(f"/knowledge-bases/{kb_id}")
    assert r.status_code == 404


def test_nonexistent_kb_returns_404(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.get(f"/knowledge-bases/{uuid.uuid4()}")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Archive side-effects — agent connections deactivated
# ═══════════════════════════════════════════════════════════════════════════════

def _make_agent_kb_connection(db: Session, workspace_id: uuid.UUID, kb_id: uuid.UUID) -> uuid.UUID:
    """Create a minimal Agent + AgentKnowledgeBase connection and return the connection id."""
    agent = Agent(
        workspace_id=workspace_id,
        name=f"Agent-{uuid.uuid4().hex[:6]}",
        status="active",
    )
    db.add(agent)
    db.flush()

    conn = AgentKnowledgeBase(
        workspace_id=workspace_id,
        agent_id=agent.id,
        knowledge_base_id=kb_id,
        is_active=True,
    )
    db.add(conn)
    db.flush()
    return conn.id


def test_archive_kb_deactivates_agent_connections(db):
    owner, ws = _setup(db)
    with _make_client(db, owner, ws) as client:
        kb_id = uuid.UUID(_post_kb(client).json()["id"])

    conn_id = _make_agent_kb_connection(db, ws.id, kb_id)
    db.commit()

    with _make_client(db, owner, ws) as client:
        client.delete(f"/knowledge-bases/{kb_id}")

    db.expire_all()
    conn = db.scalar(
        select(AgentKnowledgeBase).where(AgentKnowledgeBase.id == conn_id)
    )
    assert conn is not None
    assert conn.is_active is False
