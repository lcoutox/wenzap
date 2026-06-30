"""
Tests for catalog item plan limit enforcement.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.plan import Plan
from tests.conftest import _make_client, _make_subscription, _make_user, _make_workspace


def _plan_with_limit(db: Session, limit: int) -> Plan:
    p = Plan(
        code=f"test_catalog_limit_{limit}_{uuid.uuid4().hex[:6]}",
        name=f"Catalog Limit {limit} Plan",
        monthly_price_cents=0, currency="BRL",
        agents_limit=99, knowledge_bases_limit=99, sources_per_kb_limit=99,
        max_source_chars=9999999, users_limit=99, pipelines_limit=99,
        integrations_limit=99, catalog_items_limit=limit, channels_limit=99,
        monthly_ai_credits=99999, monthly_conversations=9999, is_active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_catalog_limit_one_blocks_second(db: Session):
    user = _make_user(db, "catalog-limit@test.com", "Catalog User")
    ws = _make_workspace(db, user, "cat-limit-ws", "Cat Limit WS")
    plan = _plan_with_limit(db, 1)
    _make_subscription(db, ws, plan)

    with _make_client(db, user, ws) as client:
        r1 = client.post("/catalog/items", json={"name": "Item 1", "status": "active"})
        assert r1.status_code == 201

        r2 = client.post("/catalog/items", json={"name": "Item 2", "status": "active"})
        assert r2.status_code == 402


def test_archived_item_does_not_count_toward_limit(db: Session):
    user = _make_user(db, "catalog-archived@test.com", "Archived Cat User")
    ws = _make_workspace(db, user, "cat-archived-ws", "Cat Archived WS")
    plan = _plan_with_limit(db, 1)
    _make_subscription(db, ws, plan)

    with _make_client(db, user, ws) as client:
        r1 = client.post("/catalog/items", json={"name": "Item 1", "status": "active"})
        assert r1.status_code == 201
        item_id = r1.json()["id"]

        client.delete(f"/catalog/items/{item_id}")

        r2 = client.post("/catalog/items", json={"name": "Item 2", "status": "active"})
        assert r2.status_code == 201


def test_no_subscription_blocks_catalog_item_creation(db: Session):
    user = _make_user(db, "catalog-nosub@test.com", "No Sub Cat User")
    ws = _make_workspace(db, user, "cat-nosub-ws", "Cat No Sub WS")

    with _make_client(db, user, ws) as client:
        r = client.post("/catalog/items", json={"name": "Item", "status": "active"})
    assert r.status_code == 402
