"""
Tests for Agent ↔ Knowledge Base connection — Phase 4.1.4.

Covers:
  1. Connect / list / disconnect
  2. Activate / deactivate (PATCH)
  3. Tenant isolation
  4. KB archived behaviour
  5. RBAC
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AgentStatus, MemberRole, MemberStatus, SubscriptionStatus
from app.models.agent import Agent
from app.models.agent_knowledge_base import AgentKnowledgeBase
from app.models.knowledge_base import KnowledgeBase
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_plan(db: Session) -> Plan:
    p = Plan(
        code=f"test-plan-{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        sources_per_kb_limit=20,
        max_source_chars=50000,
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


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(
        workspace_id=workspace_id,
        name=f"Agent-{uuid.uuid4().hex[:6]}",
        status=AgentStatus.active,
    )
    db.add(agent)
    db.flush()
    return agent


def _make_kb(
    db: Session, workspace_id: uuid.UUID, *, name: str = "Test KB", status: str = "active"
) -> KnowledgeBase:
    kb = KnowledgeBase(workspace_id=workspace_id, name=name, status=status)
    db.add(kb)
    db.flush()
    return kb


def _make_member(db: Session, workspace_id: uuid.UUID, role: MemberRole) -> object:
    from app.models.workspace_member import WorkspaceMember

    user = _make_user(db, f"{role.value}-{uuid.uuid4().hex[:6]}@test.com", role.value.title())
    db.add(WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role=role,
        status=MemberStatus.active,
    ))
    db.flush()
    return user


def _setup(db: Session):
    """Return (owner, ws, agent, kb) all ready."""
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "Test WS")
    plan = _make_plan(db)
    _make_subscription(db, ws.id, plan)
    agent = _make_agent(db, ws.id)
    kb = _make_kb(db, ws.id)
    db.commit()
    return owner, ws, agent, kb


def _connect(client, agent_id, kb_id):
    return client.post(
        f"/agents/{agent_id}/knowledge-bases",
        json={"knowledge_base_id": str(kb_id)},
    )


def _disconnect(client, agent_id, kb_id):
    return client.delete(f"/agents/{agent_id}/knowledge-bases/{kb_id}")


def _patch_conn(client, agent_id, kb_id, *, is_active: bool):
    return client.patch(
        f"/agents/{agent_id}/knowledge-bases/{kb_id}",
        json={"is_active": is_active},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Connect / list / disconnect
# ═══════════════════════════════════════════════════════════════════════════════

def test_connect_kb_returns_201(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _connect(client, agent.id, kb.id)
    assert r.status_code == 201


def test_connect_kb_response_fields(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _connect(client, agent.id, kb.id)
    body = r.json()
    assert body["agent_id"] == str(agent.id)
    assert body["knowledge_base_id"] == str(kb.id)
    assert body["is_active"] is True
    assert body["workspace_id"] == str(ws.id)


def test_connect_kb_includes_kb_name(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _connect(client, agent.id, kb.id)
    assert r.json()["knowledge_base_name"] == kb.name


def test_connect_kb_includes_kb_status(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _connect(client, agent.id, kb.id)
    assert r.json()["knowledge_base_status"] == "active"


def test_list_agent_kbs_returns_connection(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        r = client.get(f"/agents/{agent.id}/knowledge-bases")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["knowledge_base_id"] == str(kb.id)


def test_list_agent_kbs_empty_when_none(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.get(f"/agents/{agent.id}/knowledge-bases")
    assert r.status_code == 200
    assert r.json() == []


def test_disconnect_kb_returns_204(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        r = _disconnect(client, agent.id, kb.id)
    assert r.status_code == 204


def test_disconnect_removes_from_listing(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        _disconnect(client, agent.id, kb.id)
        r = client.get(f"/agents/{agent.id}/knowledge-bases")
    assert r.json() == []


def test_disconnect_nonexistent_returns_404(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _disconnect(client, agent.id, kb.id)
    assert r.status_code == 404


def test_connect_active_kb_again_returns_409(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        r = _connect(client, agent.id, kb.id)
    assert r.status_code == 409


def test_reconnect_after_disconnect_returns_201(db):
    """Hard-delete on disconnect → reconnecting creates a fresh row (201)."""
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        _disconnect(client, agent.id, kb.id)
        r = _connect(client, agent.id, kb.id)
    assert r.status_code == 201


def test_reactivate_inactive_connection_returns_200(db):
    """Deactivated connection (not deleted) is reactivated on reconnect → 200."""
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        _patch_conn(client, agent.id, kb.id, is_active=False)
        r = _connect(client, agent.id, kb.id)
    assert r.status_code == 200
    assert r.json()["is_active"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Activate / deactivate (PATCH)
# ═══════════════════════════════════════════════════════════════════════════════

def test_patch_deactivate_connection(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        r = _patch_conn(client, agent.id, kb.id, is_active=False)
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_patch_reactivate_connection(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        _patch_conn(client, agent.id, kb.id, is_active=False)
        r = _patch_conn(client, agent.id, kb.id, is_active=True)
    assert r.status_code == 200
    assert r.json()["is_active"] is True


def test_patch_nonexistent_connection_returns_404(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _patch_conn(client, agent.id, kb.id, is_active=False)
    assert r.status_code == 404


def test_inactive_connection_still_appears_in_listing(db):
    """Inactive connections are still listed (is_active=False, not deleted)."""
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        _patch_conn(client, agent.id, kb.id, is_active=False)
        r = client.get(f"/agents/{agent.id}/knowledge-bases")
    assert len(r.json()) == 1
    assert r.json()[0]["is_active"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Tenant isolation
# ═══════════════════════════════════════════════════════════════════════════════

def test_connect_agent_from_another_workspace_returns_404(db):
    owner_a, ws_a, agent_a, kb_a = _setup(db)
    owner_b, ws_b, agent_b, kb_b = _setup(db)
    with _make_client(db, owner_b, ws_b) as c_b:
        r = _connect(c_b, agent_a.id, kb_b.id)
    assert r.status_code == 404


def test_connect_kb_from_another_workspace_returns_404(db):
    owner_a, ws_a, agent_a, kb_a = _setup(db)
    owner_b, ws_b, agent_b, kb_b = _setup(db)
    with _make_client(db, owner_b, ws_b) as c_b:
        r = _connect(c_b, agent_b.id, kb_a.id)
    assert r.status_code == 404


def test_list_does_not_leak_cross_workspace_connections(db):
    owner_a, ws_a, agent_a, kb_a = _setup(db)
    owner_b, ws_b, agent_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        _connect(c_a, agent_a.id, kb_a.id)
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.get(f"/agents/{agent_b.id}/knowledge-bases")
    assert r.json() == []


def test_disconnect_cross_workspace_connection_returns_404(db):
    owner_a, ws_a, agent_a, kb_a = _setup(db)
    owner_b, ws_b, agent_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        _connect(c_a, agent_a.id, kb_a.id)
    with _make_client(db, owner_b, ws_b) as c_b:
        r = _disconnect(c_b, agent_a.id, kb_a.id)
    assert r.status_code == 404


def test_patch_cross_workspace_connection_returns_404(db):
    owner_a, ws_a, agent_a, kb_a = _setup(db)
    owner_b, ws_b, agent_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        _connect(c_a, agent_a.id, kb_a.id)
    with _make_client(db, owner_b, ws_b) as c_b:
        r = _patch_conn(c_b, agent_a.id, kb_a.id, is_active=False)
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 4. KB archived behaviour
# ═══════════════════════════════════════════════════════════════════════════════

def test_connect_archived_kb_returns_404(db):
    owner, ws, agent, _ = _setup(db)
    archived_kb = _make_kb(db, ws.id, status="archived")
    db.commit()
    with _make_client(db, owner, ws) as client:
        r = _connect(client, agent.id, archived_kb.id)
    assert r.status_code == 404


def test_archived_kb_not_in_listing(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        # Archive the KB via the KB endpoint (triggers deactivation in service)
        client.delete(f"/knowledge-bases/{kb.id}")
        r = client.get(f"/agents/{agent.id}/knowledge-bases")
    assert r.json() == []


def test_archive_kb_deactivates_connection(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)

    # Get connection id from DB
    conn = db.scalar(
        select(AgentKnowledgeBase).where(
            AgentKnowledgeBase.agent_id == agent.id,
            AgentKnowledgeBase.knowledge_base_id == kb.id,
        )
    )
    assert conn is not None

    with _make_client(db, owner, ws) as client:
        client.delete(f"/knowledge-bases/{kb.id}")

    db.expire_all()
    conn = db.scalar(select(AgentKnowledgeBase).where(AgentKnowledgeBase.id == conn.id))
    assert conn.is_active is False


def test_patch_connection_to_archived_kb_returns_404(db):
    owner, ws, agent, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        _connect(client, agent.id, kb.id)
        client.delete(f"/knowledge-bases/{kb.id}")
        r = _patch_conn(client, agent.id, kb.id, is_active=True)
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 5. RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_viewer_can_list_connections(db):
    owner, ws, agent, kb = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        _connect(c_owner, agent.id, kb.id)
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.get(f"/agents/{agent.id}/knowledge-bases")
    assert r.status_code == 200


def test_viewer_cannot_connect_kb(db):
    owner, ws, agent, kb = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, viewer, ws) as c_viewer:
        r = _connect(c_viewer, agent.id, kb.id)
    assert r.status_code == 403


def test_viewer_cannot_disconnect_kb(db):
    owner, ws, agent, kb = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        _connect(c_owner, agent.id, kb.id)
    with _make_client(db, viewer, ws) as c_viewer:
        r = _disconnect(c_viewer, agent.id, kb.id)
    assert r.status_code == 403


def test_viewer_cannot_patch_connection(db):
    owner, ws, agent, kb = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        _connect(c_owner, agent.id, kb.id)
    with _make_client(db, viewer, ws) as c_viewer:
        r = _patch_conn(c_viewer, agent.id, kb.id, is_active=False)
    assert r.status_code == 403


def test_member_can_connect_kb(db):
    owner, ws, agent, kb = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    db.commit()
    with _make_client(db, member, ws) as c_member:
        r = _connect(c_member, agent.id, kb.id)
    assert r.status_code == 201


def test_member_can_disconnect_kb(db):
    owner, ws, agent, kb = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        _connect(c_owner, agent.id, kb.id)
    with _make_client(db, member, ws) as c_member:
        r = _disconnect(c_member, agent.id, kb.id)
    assert r.status_code == 204


def test_member_can_patch_connection(db):
    owner, ws, agent, kb = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        _connect(c_owner, agent.id, kb.id)
    with _make_client(db, member, ws) as c_member:
        r = _patch_conn(c_member, agent.id, kb.id, is_active=False)
    assert r.status_code == 200


def test_admin_can_connect_and_disconnect_kb(db):
    owner, ws, agent, kb = _setup(db)
    admin = _make_member(db, ws.id, MemberRole.admin)
    db.commit()
    with _make_client(db, admin, ws) as c_admin:
        r1 = _connect(c_admin, agent.id, kb.id)
        r2 = _disconnect(c_admin, agent.id, kb.id)
    assert r1.status_code == 201
    assert r2.status_code == 204
