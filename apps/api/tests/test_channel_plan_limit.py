"""
Tests for channel plan limit enforcement.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.plan import Plan
from tests.conftest import _make_client, _make_subscription, _make_user, _make_workspace


def _plan_with_channels_limit(db: Session, limit: int) -> Plan:
    from sqlalchemy import select as _sel  # noqa: PLC0415

    p = db.scalar(_sel(Plan).where(Plan.code == "starter"))
    if p is None:
        p = Plan(
            code="starter",
            name=f"Channels Limit {limit} Plan",
            monthly_price_cents=0, currency="BRL",
            agents_limit=99, knowledge_bases_limit=99, sources_per_kb_limit=99,
            max_source_chars=9999999, users_limit=99, pipelines_limit=99,
            integrations_limit=99, catalog_items_limit=9999, channels_limit=limit,
            monthly_ai_credits=99999, monthly_conversations=9999, is_active=True,
        )
        db.add(p)
    else:
        p.channels_limit = limit
    db.commit()
    db.refresh(p)
    return p


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Test Agent", status="active")
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def test_channel_limit_one_blocks_second(db: Session, feature_matrix):
    user = _make_user(db, "channel-limit@test.com", "Channel Limit User")
    ws = _make_workspace(db, user, "ch-limit-ws", "Ch Limit WS")
    plan = _plan_with_channels_limit(db, 1)
    _make_subscription(db, ws, plan)
    agent = _make_agent(db, ws.id)

    payload = {"agent_id": str(agent.id), "channel_type": "web_widget", "name": "Widget"}

    with _make_client(db, user, ws) as client:
        r1 = client.post("/channels", json=payload)
        assert r1.status_code == 201

        r2 = client.post("/channels", json={**payload, "name": "Widget 2"})
        assert r2.status_code == 402


def test_archived_channel_does_not_count_toward_limit(db: Session, feature_matrix):
    user = _make_user(db, "channel-archived@test.com", "Ch Archived User")
    ws = _make_workspace(db, user, "ch-archived-ws", "Ch Archived WS")
    plan = _plan_with_channels_limit(db, 1)
    _make_subscription(db, ws, plan)
    agent = _make_agent(db, ws.id)

    payload = {"agent_id": str(agent.id), "channel_type": "web_widget", "name": "Widget"}

    with _make_client(db, user, ws) as client:
        r1 = client.post("/channels", json=payload)
        assert r1.status_code == 201
        ch_id = r1.json()["id"]

        client.post(f"/channels/{ch_id}/archive")

        r2 = client.post("/channels", json={**payload, "name": "Widget 2"})
        assert r2.status_code == 201


def test_no_subscription_blocks_channel_creation(db: Session):
    user = _make_user(db, "channel-nosub@test.com", "No Sub Ch User")
    ws = _make_workspace(db, user, "ch-nosub-ws", "Ch No Sub WS")
    agent = _make_agent(db, ws.id)

    payload = {"agent_id": str(agent.id), "channel_type": "web_widget", "name": "Widget"}

    with _make_client(db, user, ws) as client:
        r = client.post("/channels", json=payload)
    assert r.status_code == 402
