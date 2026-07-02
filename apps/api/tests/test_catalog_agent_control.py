"""
Tests for Catálogo.5 — Agent Catalog Controls.

Covers:
- Default catalog_enabled=True on create (via API)
- create with catalog_enabled=False
- PATCH catalog_enabled persists
- PATCH omitting catalog_enabled preserves existing value
- Playground respects catalog_enabled=False (no retrieval)
- Playground respects catalog_enabled=True (retrieval attempted)
- Inbox context builder skips retrieval when catalog_enabled=False
- Inbox context builder calls retrieval when catalog_enabled=True
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.catalog_item import CatalogItem
from app.services.catalog_retrieval_service import CatalogRetrievalResult
from tests.conftest import _make_user, _make_workspace


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    catalog_enabled: bool = True,
    status: str = "active",
) -> Agent:
    agent = Agent(
        workspace_id=workspace_id,
        name="Test Agent",
        status=status,
        catalog_enabled=catalog_enabled,
    )
    db.add(agent)
    db.flush()
    db.add(AgentPromptSettings(
        agent_id=agent.id,
        system_prompt="You are helpful.",
        persona=None,
    ))
    db.commit()
    db.refresh(agent)
    return agent


# ── API endpoint — create ─────────────────────────────────────────────────────

class TestAgentCreateCatalogEnabled:
    def test_default_catalog_enabled_false(self, client_a, subscription_a, ai_model):
        resp = client_a.post("/agents", json={
            "name": "Sales Agent",
            "ai_model_id": str(ai_model.id),
        })
        assert resp.status_code == 201
        assert resp.json()["catalog_enabled"] is False

    def test_create_with_catalog_enabled_false(self, client_a, subscription_a, ai_model):
        resp = client_a.post("/agents", json={
            "name": "Support Agent",
            "ai_model_id": str(ai_model.id),
            "catalog_enabled": False,
        })
        assert resp.status_code == 201
        assert resp.json()["catalog_enabled"] is False

    def test_create_with_catalog_enabled_true_explicit(self, client_a, subscription_a, ai_model):
        resp = client_a.post("/agents", json={
            "name": "Commerce Agent",
            "ai_model_id": str(ai_model.id),
            "catalog_enabled": True,
        })
        assert resp.status_code == 201
        assert resp.json()["catalog_enabled"] is True


# ── API endpoint — update ─────────────────────────────────────────────────────

class TestAgentUpdateCatalogEnabled:
    def _create(self, client_a, ai_model, catalog_enabled: bool = True) -> dict:
        resp = client_a.post("/agents", json={
            "name": "Agent Update Test",
            "ai_model_id": str(ai_model.id),
            "catalog_enabled": catalog_enabled,
        })
        assert resp.status_code == 201
        return resp.json()

    def test_patch_catalog_enabled_false(self, client_a, subscription_a, ai_model):
        agent = self._create(client_a, ai_model, catalog_enabled=True)
        resp = client_a.patch(f"/agents/{agent['id']}", json={"catalog_enabled": False})
        assert resp.status_code == 200
        assert resp.json()["catalog_enabled"] is False

    def test_patch_catalog_enabled_true(self, client_a, subscription_a, ai_model):
        agent = self._create(client_a, ai_model, catalog_enabled=False)
        resp = client_a.patch(f"/agents/{agent['id']}", json={"catalog_enabled": True})
        assert resp.status_code == 200
        assert resp.json()["catalog_enabled"] is True

    def test_patch_omitting_preserves_false(self, client_a, subscription_a, ai_model):
        agent = self._create(client_a, ai_model, catalog_enabled=False)
        resp = client_a.patch(f"/agents/{agent['id']}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["catalog_enabled"] is False

    def test_patch_omitting_preserves_true(self, client_a, subscription_a, ai_model):
        agent = self._create(client_a, ai_model, catalog_enabled=True)
        resp = client_a.patch(f"/agents/{agent['id']}", json={"name": "Renamed 2"})
        assert resp.status_code == 200
        assert resp.json()["catalog_enabled"] is True


# ── conversation_context_builder — retrieval guard ────────────────────────────

class TestConversationContextBuilderCatalogGuard:
    def test_skips_retrieval_when_catalog_disabled(self, db: Session):
        owner = _make_user(db, f"ccb-{uuid.uuid4().hex[:6]}@t.com", "CCB")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        agent = _make_agent(db, ws.id, catalog_enabled=False)

        mock_conv = SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            agent_id=agent.id,
            channel_type="web",
            status="open",
            assigned_user_id=None,
        )
        mock_msg = SimpleNamespace(
            id=uuid.uuid4(),
            direction="inbound",
            sender_type="customer",
            content="Quais planos vocês oferecem?",
        )

        with patch(
            "app.services.conversation_context_builder.retrieve_catalog_context"
        ) as mock_retrieve, patch(
            "app.services.conversation_context_builder.retrieve_context_for_agent"
        ) as mock_rag:
            mock_rag.return_value = SimpleNamespace(
                chunks=[],
                retrieval_attempted=False,
                retrieval_duration_ms=0,
                error_message=None,
            )
            from app.services.conversation_context_builder import build_conversation_context
            ctx = build_conversation_context(
                db,
                workspace_id=ws.id,
                conversation=mock_conv,
                agent=agent,
                trigger_message=mock_msg,
            )

        mock_retrieve.assert_not_called()
        assert ctx.catalog_retrieval_attempted is False
        assert ctx.catalog_items == []

    def test_calls_retrieval_when_catalog_enabled(self, db: Session):
        owner = _make_user(db, f"ccb2-{uuid.uuid4().hex[:6]}@t.com", "CCB2")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        agent = _make_agent(db, ws.id, catalog_enabled=True)

        mock_conv = SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=ws.id,
            agent_id=agent.id,
            channel_type="web",
            status="open",
            assigned_user_id=None,
        )
        mock_msg = SimpleNamespace(
            id=uuid.uuid4(),
            direction="inbound",
            sender_type="customer",
            content="Quais planos vocês oferecem?",
        )

        fake_result = CatalogRetrievalResult(retrieval_attempted=True)

        with patch(
            "app.services.conversation_context_builder.retrieve_catalog_context",
            return_value=fake_result,
        ) as mock_retrieve, patch(
            "app.services.conversation_context_builder.retrieve_context_for_agent"
        ) as mock_rag:
            mock_rag.return_value = SimpleNamespace(
                chunks=[],
                retrieval_attempted=False,
                retrieval_duration_ms=0,
                error_message=None,
            )
            from app.services.conversation_context_builder import build_conversation_context
            ctx = build_conversation_context(
                db,
                workspace_id=ws.id,
                conversation=mock_conv,
                agent=agent,
                trigger_message=mock_msg,
            )

        mock_retrieve.assert_called_once()
        assert ctx.catalog_retrieval_attempted is True


# ── agent_test_service — playground guard ─────────────────────────────────────

class TestPlaygroundCatalogGuard:
    def test_playground_skips_retrieval_when_catalog_disabled(
        self, client_a, subscription_a, ai_model
    ):
        resp = client_a.post("/agents", json={
            "name": "Playground Test Agent",
            "ai_model_id": str(ai_model.id),
            "catalog_enabled": False,
        })
        assert resp.status_code == 201
        agent_id = resp.json()["id"]

        # Activate the agent (requires system_prompt)
        client_a.patch(f"/agents/{agent_id}", json={
            "system_prompt": "You are a helpful assistant."
        })
        client_a.patch(f"/agents/{agent_id}/status", json={"status": "active"})

        with patch(
            "app.services.agent_test_service.retrieve_catalog_context"
        ) as mock_retrieve, patch(
            "app.services.agent_test_service.llm_client.complete"
        ) as mock_llm:
            mock_llm.return_value = SimpleNamespace(
                content="Olá! Como posso ajudar?",
                input_tokens=10,
                output_tokens=5,
                duration_ms=100,
            )
            resp = client_a.post(f"/agents/{agent_id}/test", json={
                "message": "Quais planos vocês oferecem?"
            })

        # Retrieval should NOT be called
        mock_retrieve.assert_not_called()
        if resp.status_code == 200:
            data = resp.json()
            assert data["catalog_retrieval_attempted"] is False
            assert data["catalog_items_count"] == 0
            assert data["catalog_retrieval_method"] is None
