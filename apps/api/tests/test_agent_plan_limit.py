"""
Tests for the agent plan limit enforcement.

Rules:
- Archived agents do not count toward the limit.
- Workspaces without a subscription cannot create agents.
- When limit is reached, POST /agents returns 402.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.plan import Plan
from tests.conftest import _make_client, _make_subscription, _make_user, _make_workspace

AGENT_PAYLOAD = {"name": "Agent", "system_prompt": "Hello"}


def _plan_with_limit(db: Session, limit: int) -> Plan:
    import uuid
    p = Plan(
        code=f"test_limit_{limit}_{uuid.uuid4().hex[:6]}",
        name=f"Limit {limit} Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=limit,
        knowledge_bases_limit=5,
        users_limit=10,
        pipelines_limit=5,
        integrations_limit=5,
        monthly_ai_credits=10000,
        monthly_conversations=5000,
        is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_starter_limit_one_agent_blocks_second(db):
    """Workspace on a 1-agent plan cannot create a second non-archived agent."""
    user = _make_user(db, "starter@test.com", "Starter User")
    ws = _make_workspace(db, user, "starter-ws", "Starter WS")
    plan = _plan_with_limit(db, 1)
    _make_subscription(db, ws, plan)

    with _make_client(db, user, ws) as client:
        r1 = client.post("/agents", json=AGENT_PAYLOAD)
        assert r1.status_code == 201

        r2 = client.post("/agents", json={"name": "Second Agent"})
        assert r2.status_code == 402


def test_archived_agent_does_not_count_toward_limit(db):
    """If the only agent is archived, a new one can be created."""
    user = _make_user(db, "archived@test.com", "Archived User")
    ws = _make_workspace(db, user, "archived-ws", "Archived WS")
    plan = _plan_with_limit(db, 1)
    _make_subscription(db, ws, plan)

    with _make_client(db, user, ws) as client:
        r1 = client.post("/agents", json=AGENT_PAYLOAD)
        assert r1.status_code == 201
        agent_id = r1.json()["id"]

        # Archive the agent
        client.patch(f"/agents/{agent_id}/status", json={"status": "archived"})

        # Now we should be able to create another
        r2 = client.post("/agents", json={"name": "New Agent"})
        assert r2.status_code == 201


def test_growth_limit_five_blocks_sixth(db):
    """Workspace on a 5-agent plan cannot create a sixth non-archived agent."""
    user = _make_user(db, "growth@test.com", "Growth User")
    ws = _make_workspace(db, user, "growth-ws", "Growth WS")
    plan = _plan_with_limit(db, 5)
    _make_subscription(db, ws, plan)

    with _make_client(db, user, ws) as client:
        for i in range(5):
            r = client.post("/agents", json={"name": f"Agent {i+1}"})
            assert r.status_code == 201

        r6 = client.post("/agents", json={"name": "Agent 6"})
        assert r6.status_code == 402


def test_no_subscription_blocks_agent_creation(db):
    """Workspace without subscription cannot create agents."""
    user = _make_user(db, "nosub@test.com", "No Sub User")
    ws = _make_workspace(db, user, "nosub-ws", "No Sub WS")
    # No subscription created

    with _make_client(db, user, ws) as client:
        response = client.post("/agents", json=AGENT_PAYLOAD)
    assert response.status_code == 402


def test_canceled_subscription_blocks_agent_creation(db):
    """Workspace with a canceled subscription cannot create agents."""
    user = _make_user(db, "canceled@test.com", "Canceled User")
    ws = _make_workspace(db, user, "canceled-ws", "Canceled WS")
    plan = _plan_with_limit(db, 5)

    now = datetime.now(timezone.utc)
    from app.models.workspace_subscription import WorkspaceSubscription
    sub = WorkspaceSubscription(
        workspace_id=ws.id,
        plan_id=plan.id,
        status="canceled",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    db.commit()

    with _make_client(db, user, ws) as client:
        response = client.post("/agents", json=AGENT_PAYLOAD)
    assert response.status_code == 402


def test_past_due_subscription_blocks_agent_creation(db):
    """Workspace with a past_due subscription cannot create agents."""
    user = _make_user(db, "pastdue@test.com", "Past Due User")
    ws = _make_workspace(db, user, "pastdue-ws", "Past Due WS")
    plan = _plan_with_limit(db, 5)

    now = datetime.now(timezone.utc)
    from app.models.workspace_subscription import WorkspaceSubscription
    sub = WorkspaceSubscription(
        workspace_id=ws.id,
        plan_id=plan.id,
        status="past_due",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    db.commit()

    with _make_client(db, user, ws) as client:
        response = client.post("/agents", json=AGENT_PAYLOAD)
    assert response.status_code == 402


def test_inactive_agents_count_toward_limit(db):
    """Inactive agents (not archived) still consume the limit."""
    user = _make_user(db, "inactive-limit@test.com", "Inactive Limit User")
    ws = _make_workspace(db, user, "inactive-limit-ws", "Inactive Limit WS")
    plan = _plan_with_limit(db, 1)
    _make_subscription(db, ws, plan)

    with _make_client(db, user, ws) as client:
        r1 = client.post("/agents", json={**AGENT_PAYLOAD})
        assert r1.status_code == 201
        agent_id = r1.json()["id"]

        # Activate then deactivate — still counts
        client.patch(f"/agents/{agent_id}/status", json={"status": "active"})
        client.patch(f"/agents/{agent_id}/status", json={"status": "inactive"})

        r2 = client.post("/agents", json={"name": "Second Agent"})
        assert r2.status_code == 402
