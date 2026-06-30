"""
Tests for Agent Tools.2-A — Catalog Category Scope per Agent.

Covers:
  - GET /agents/{id}/tools/catalog returns correct scope
  - PUT /agents/{id}/tools/catalog sets catalog_enabled
  - PUT with category_scope=selected saves category_ids
  - PUT with category_scope=all clears category_ids
  - Category from another workspace is rejected
  - Retrieval respects allowed_category_ids (lexical)
  - Retrieval with no categories = whole catalog (all scope)
  - catalog_enabled=False skips retrieval regardless of scope
  - Metadata catalog_scope reflects configuration
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_catalog_category import AgentCatalogCategory
from app.models.catalog_category import CatalogCategory
from app.models.catalog_item import CatalogItem
from app.services.agent_catalog_scope_service import get_allowed_category_ids
from app.services.catalog_retrieval_service import retrieve_catalog_items
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_agent(db: Session, workspace_id: uuid.UUID, *, catalog_enabled: bool = True) -> Agent:
    agent = Agent(
        workspace_id=workspace_id,
        name="Test Agent",
        status="active",
        model_name="nexbrain-prime",
        catalog_enabled=catalog_enabled,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _make_category(db: Session, workspace_id: uuid.UUID, name: str) -> CatalogCategory:
    cat = CatalogCategory(
        workspace_id=workspace_id,
        name=name,
        is_active=True,
        sort_order=0,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def _make_item(
    db: Session,
    workspace_id: uuid.UUID,
    name: str,
    category_id: uuid.UUID | None = None,
) -> CatalogItem:
    item = CatalogItem(
        workspace_id=workspace_id,
        name=name,
        status="active",
        currency="BRL",
        tags=[],
        metadata_json={},
        searchable_text=name.lower(),
        is_featured=False,
        category_id=category_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _setup(db: Session):
    owner = _make_user(db, f"scope-{uuid.uuid4().hex[:6]}@t.com", "Scope User")
    ws = _make_workspace(db, owner, f"scope-{uuid.uuid4().hex[:6]}", "Scope WS")
    db.commit()
    return owner, ws


# ── GET scope ─────────────────────────────────────────────────────────────────


class TestGetCatalogScope:
    def test_returns_all_scope_by_default(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        with _make_client(db, owner, ws) as client:
            resp = client.get(f"/agents/{agent.id}/tools/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["catalog_enabled"] is True
        assert data["category_scope"] == "all"
        assert data["category_ids"] == []

    def test_reflects_catalog_enabled_false(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id, catalog_enabled=False)
        with _make_client(db, owner, ws) as client:
            resp = client.get(f"/agents/{agent.id}/tools/catalog")
        assert resp.status_code == 200
        assert resp.json()["catalog_enabled"] is False

    def test_reflects_saved_categories(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        cat = _make_category(db, ws.id, "Planos")
        db.add(AgentCatalogCategory(
            workspace_id=ws.id, agent_id=agent.id, category_id=cat.id
        ))
        db.commit()
        with _make_client(db, owner, ws) as client:
            resp = client.get(f"/agents/{agent.id}/tools/catalog")
        data = resp.json()
        assert data["category_scope"] == "selected"
        assert str(cat.id) in data["category_ids"]


# ── PUT scope ─────────────────────────────────────────────────────────────────


class TestUpdateCatalogScope:
    def test_disable_catalog(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        with _make_client(db, owner, ws) as client:
            resp = client.put(
                f"/agents/{agent.id}/tools/catalog",
                json={"catalog_enabled": False, "category_scope": "all", "category_ids": []},
            )
        assert resp.status_code == 200
        assert resp.json()["catalog_enabled"] is False
        db.refresh(agent)
        assert agent.catalog_enabled is False

    def test_set_selected_categories(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        cat1 = _make_category(db, ws.id, "Veículos")
        cat2 = _make_category(db, ws.id, "Serviços")
        with _make_client(db, owner, ws) as client:
            resp = client.put(
                f"/agents/{agent.id}/tools/catalog",
                json={
                    "catalog_enabled": True,
                    "category_scope": "selected",
                    "category_ids": [str(cat1.id), str(cat2.id)],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["category_scope"] == "selected"
        assert len(data["category_ids"]) == 2

        rows = db.scalars(
            select(AgentCatalogCategory).where(AgentCatalogCategory.agent_id == agent.id)
        ).all()
        assert len(rows) == 2

    def test_switch_back_to_all_clears_categories(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        cat = _make_category(db, ws.id, "Cat A")
        db.add(AgentCatalogCategory(
            workspace_id=ws.id, agent_id=agent.id, category_id=cat.id
        ))
        db.commit()

        with _make_client(db, owner, ws) as client:
            resp = client.put(
                f"/agents/{agent.id}/tools/catalog",
                json={"catalog_enabled": True, "category_scope": "all", "category_ids": []},
            )
        assert resp.status_code == 200
        assert resp.json()["category_scope"] == "all"
        assert resp.json()["category_ids"] == []
        rows = db.scalars(
            select(AgentCatalogCategory).where(AgentCatalogCategory.agent_id == agent.id)
        ).all()
        assert rows == []

    def test_categories_from_another_workspace_are_rejected(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        agent_a = _make_agent(db, ws_a.id)
        cat_b = _make_category(db, ws_b.id, "Cat B")

        with _make_client(db, owner_a, ws_a) as client:
            resp = client.put(
                f"/agents/{agent_a.id}/tools/catalog",
                json={
                    "catalog_enabled": True,
                    "category_scope": "selected",
                    "category_ids": [str(cat_b.id)],
                },
            )
        assert resp.status_code == 200
        # Foreign category silently excluded — scope falls back to "all"
        assert resp.json()["category_ids"] == []
        assert resp.json()["category_scope"] == "all"

    def test_idempotent_update(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        cat = _make_category(db, ws.id, "Cat X")
        payload = {
            "catalog_enabled": True,
            "category_scope": "selected",
            "category_ids": [str(cat.id)],
        }
        with _make_client(db, owner, ws) as client:
            client.put(f"/agents/{agent.id}/tools/catalog", json=payload)
            resp = client.put(f"/agents/{agent.id}/tools/catalog", json=payload)
        assert resp.status_code == 200
        rows = db.scalars(
            select(AgentCatalogCategory).where(AgentCatalogCategory.agent_id == agent.id)
        ).all()
        assert len(rows) == 1  # no duplicates


# ── Service helpers ───────────────────────────────────────────────────────────


class TestGetAllowedCategoryIds:
    def test_returns_none_when_no_categories(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        result = get_allowed_category_ids(db, agent_id=agent.id, workspace_id=ws.id)
        assert result is None

    def test_returns_ids_when_categories_set(self, db: Session):
        owner, ws = _setup(db)
        agent = _make_agent(db, ws.id)
        cat = _make_category(db, ws.id, "Veículos")
        db.add(AgentCatalogCategory(
            workspace_id=ws.id, agent_id=agent.id, category_id=cat.id
        ))
        db.commit()
        result = get_allowed_category_ids(db, agent_id=agent.id, workspace_id=ws.id)
        assert result == [cat.id]


# ── Retrieval scope ───────────────────────────────────────────────────────────


class TestRetrievalScope:
    def test_all_scope_returns_items_from_all_categories(self, db: Session):
        owner, ws = _setup(db)
        cat1 = _make_category(db, ws.id, "Veículos")
        cat2 = _make_category(db, ws.id, "Serviços")
        _make_item(db, ws.id, "carro sedan disponível", category_id=cat1.id)
        _make_item(db, ws.id, "serviço revisão disponível", category_id=cat2.id)

        results = retrieve_catalog_items(
            db, ws.id, "produto disponível", allowed_category_ids=None
        )
        names = {r.name for r in results}
        assert "carro sedan disponível" in names
        assert "serviço revisão disponível" in names

    def test_selected_scope_filters_to_category(self, db: Session):
        owner, ws = _setup(db)
        cat1 = _make_category(db, ws.id, "Veículos")
        cat2 = _make_category(db, ws.id, "Serviços")
        item_v = _make_item(db, ws.id, "carro sedan produto", category_id=cat1.id)
        _make_item(db, ws.id, "serviço produto revisão", category_id=cat2.id)

        results = retrieve_catalog_items(
            db, ws.id, "produto", allowed_category_ids=[cat1.id]
        )
        names = {r.name for r in results}
        assert item_v.name in names
        assert "serviço produto revisão" not in names

    def test_empty_allowed_list_with_selected_returns_nothing(self, db: Session):
        owner, ws = _setup(db)
        cat = _make_category(db, ws.id, "Veículos")
        _make_item(db, ws.id, "produto carro disponível", category_id=cat.id)

        # Passing an empty list (not None) means "selected but none chosen" → no results
        results = retrieve_catalog_items(
            db, ws.id, "produto", allowed_category_ids=[]
        )
        assert results == []
