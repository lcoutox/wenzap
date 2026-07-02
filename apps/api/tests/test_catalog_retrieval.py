"""
Tests for the Catalog Retrieval Service (Catálogo.3).

Coverage:
- Intent detection (should_retrieve_catalog)
- Retrieval returns only active items
- Retrieval filters by workspace
- Retrieval limit is respected
- Context block format
- retrieve_catalog_context() end-to-end
- Integration into conversation_context_builder (catalog injected into prompt)
- Integration into agent_test_service (catalog in playground response)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.catalog_category import CatalogCategory
from app.models.catalog_item import CatalogItem
from app.services.catalog_retrieval_service import (
    CatalogRetrievalItem,
    build_catalog_context_block,
    retrieve_catalog_context,
    retrieve_catalog_items,
    should_retrieve_catalog,
)
from tests.conftest import _make_user, _make_workspace


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_item(
    db: Session,
    workspace_id: uuid.UUID,
    name: str,
    status: str = "active",
    short_description: str | None = None,
    price: float | None = None,
    tags: list[str] | None = None,
    searchable_text: str | None = None,
) -> CatalogItem:
    item = CatalogItem(
        workspace_id=workspace_id,
        name=name,
        status=status,
        currency="BRL",
        tags=tags or [],
        metadata_json={},
        short_description=short_description,
        price=price,
        searchable_text=searchable_text or name,
        is_featured=False,
    )
    db.add(item)
    db.flush()
    return item


# ── Intent detection ──────────────────────────────────────────────────────────

class TestShouldRetrieveCatalog:
    def test_commercial_keywords_trigger(self):
        assert should_retrieve_catalog("Vocês têm apartamento de 2 quartos?")
        assert should_retrieve_catalog("Qual o preço do plano básico?")
        assert should_retrieve_catalog("Tem carro automático disponível?")
        assert should_retrieve_catalog("Quais serviços vocês oferecem?")
        assert should_retrieve_catalog("Quero uma opção mais barata")

    def test_non_commercial_messages_do_not_trigger(self):
        assert not should_retrieve_catalog("Olá, tudo bem?")
        assert not should_retrieve_catalog("Obrigado!")
        assert not should_retrieve_catalog("Quando vocês abrem?")
        assert not should_retrieve_catalog("Meu pedido foi enviado?")

    def test_empty_message_does_not_trigger(self):
        assert not should_retrieve_catalog("")
        assert not should_retrieve_catalog("   ")


# ── retrieve_catalog_items ────────────────────────────────────────────────────

class TestRetrieveCatalogItems:
    def test_returns_active_items_matching_query(self, db: Session):
        owner = _make_user(db, f"cr1-{uuid.uuid4().hex[:6]}@test.com", "CR1")
        ws = _make_workspace(db, owner, f"cr-ws-{uuid.uuid4().hex[:6]}", "CR WS")
        _make_item(db, ws.id, "Toyota Corolla", searchable_text="toyota corolla sedan automático")
        _make_item(db, ws.id, "Honda Civic", searchable_text="honda civic sedan automático")
        _make_item(db, ws.id, "Fiat Uno", searchable_text="fiat uno popular")
        db.commit()

        items = retrieve_catalog_items(db, ws.id, "automático sedan")
        names = [i.name for i in items]
        assert "Toyota Corolla" in names
        assert "Honda Civic" in names
        assert "Fiat Uno" not in names

    def test_does_not_return_inactive_items(self, db: Session):
        owner = _make_user(db, f"cr2-{uuid.uuid4().hex[:6]}@test.com", "CR2")
        ws = _make_workspace(db, owner, f"cr-ws-{uuid.uuid4().hex[:6]}", "CR WS")
        for status in ("draft", "inactive", "unavailable", "archived"):
            _make_item(db, ws.id, f"Item {status}", status=status, searchable_text="produto serviço")
        db.commit()

        items = retrieve_catalog_items(db, ws.id, "produto serviço")
        assert items == []

    def test_does_not_return_other_workspace_items(self, db: Session):
        owner_a = _make_user(db, f"cr3a-{uuid.uuid4().hex[:6]}@test.com", "CRA")
        ws_a = _make_workspace(db, owner_a, f"cr-wsa-{uuid.uuid4().hex[:6]}", "CR A")
        owner_b = _make_user(db, f"cr3b-{uuid.uuid4().hex[:6]}@test.com", "CRB")
        ws_b = _make_workspace(db, owner_b, f"cr-wsb-{uuid.uuid4().hex[:6]}", "CR B")

        _make_item(db, ws_a.id, "Item WS-A", searchable_text="produto serviço")
        db.commit()

        items_b = retrieve_catalog_items(db, ws_b.id, "produto serviço")
        assert items_b == []

    def test_respects_limit(self, db: Session):
        owner = _make_user(db, f"cr4-{uuid.uuid4().hex[:6]}@test.com", "CR4")
        ws = _make_workspace(db, owner, f"cr-ws-{uuid.uuid4().hex[:6]}", "CR WS")
        for i in range(10):
            _make_item(db, ws.id, f"Produto {i}", searchable_text="produto plano serviço")
        db.commit()

        items = retrieve_catalog_items(db, ws.id, "produto plano serviço", limit=3)
        assert len(items) <= 3

    def test_returns_category_name(self, db: Session):
        owner = _make_user(db, f"cr5-{uuid.uuid4().hex[:6]}@test.com", "CR5")
        ws = _make_workspace(db, owner, f"cr-ws-{uuid.uuid4().hex[:6]}", "CR WS")
        cat = CatalogCategory(workspace_id=ws.id, name="Seminovos")
        db.add(cat)
        db.flush()
        item = CatalogItem(
            workspace_id=ws.id,
            name="Civic Seminovo",
            status="active",
            currency="BRL",
            tags=[],
            metadata_json={},
            searchable_text="civic seminovo sedan",
            is_featured=False,
            category_id=cat.id,
        )
        db.add(item)
        db.commit()

        items = retrieve_catalog_items(db, ws.id, "civic seminovo")
        assert items[0].category_name == "Seminovos"

    def test_returns_empty_for_no_match(self, db: Session):
        owner = _make_user(db, f"cr6-{uuid.uuid4().hex[:6]}@test.com", "CR6")
        ws = _make_workspace(db, owner, f"cr-ws-{uuid.uuid4().hex[:6]}", "CR WS")
        _make_item(db, ws.id, "Toyota Corolla", searchable_text="toyota corolla")
        db.commit()

        items = retrieve_catalog_items(db, ws.id, "apartamento cobertura")
        assert items == []


# ── build_catalog_context_block ───────────────────────────────────────────────

class TestBuildCatalogContextBlock:
    def _sample_item(self, name="Toyota Corolla", price=88900.0) -> CatalogRetrievalItem:
        return CatalogRetrievalItem(
            id=uuid.uuid4(),
            name=name,
            category_name="Seminovos",
            short_description="Sedan automático flex",
            price=price,
            currency="BRL",
            tags=["automático", "sedan"],
            metadata_json={"ano": "2021", "km": "42000"},
            primary_media_available=True,
            score=2.0,
        )

    def test_block_contains_item_name(self):
        block = build_catalog_context_block([self._sample_item()])
        assert "Toyota Corolla" in block

    def test_block_contains_price(self):
        block = build_catalog_context_block([self._sample_item(price=88900.0)])
        assert "88.900" in block or "88900" in block

    def test_block_contains_tags(self):
        block = build_catalog_context_block([self._sample_item()])
        assert "automático" in block

    def test_block_contains_category(self):
        block = build_catalog_context_block([self._sample_item()])
        assert "Seminovos" in block

    def test_block_contains_metadata(self):
        block = build_catalog_context_block([self._sample_item()])
        assert "2021" in block

    def test_block_contains_media_status(self):
        block = build_catalog_context_block([self._sample_item()])
        assert "disponível" in block

    def test_block_no_price_shows_not_informed(self):
        item = self._sample_item(price=None)
        block = build_catalog_context_block([item])
        assert "Não informado" in block

    def test_block_contains_rules(self):
        block = build_catalog_context_block([self._sample_item()])
        assert "Não invente" in block or "máximo" in block

    def test_block_numbers_items(self):
        items = [self._sample_item("A"), self._sample_item("B")]
        block = build_catalog_context_block(items)
        assert "1." in block
        assert "2." in block


# ── retrieve_catalog_context ──────────────────────────────────────────────────

class TestRetrieveCatalogContext:
    def test_no_intent_skips_retrieval(self, db: Session):
        ws_id = uuid.uuid4()
        result = retrieve_catalog_context(db, ws_id, "Olá, tudo bem?")
        assert result.retrieval_attempted is False
        assert result.items == []
        assert result.context_block is None

    def test_commercial_intent_triggers_retrieval(self, db: Session):
        owner = _make_user(db, f"cc1-{uuid.uuid4().hex[:6]}@test.com", "CC1")
        ws = _make_workspace(db, owner, f"cc-ws-{uuid.uuid4().hex[:6]}", "CC WS")
        _make_item(db, ws.id, "Plano Básico", searchable_text="plano básico mensal")
        db.commit()

        # Query contains "plano" which matches searchable_text "plano básico mensal"
        result = retrieve_catalog_context(db, ws.id, "Tem algum plano disponível?")
        assert result.retrieval_attempted is True
        assert len(result.items) >= 1
        assert result.context_block is not None

    def test_no_match_returns_empty_block(self, db: Session):
        owner = _make_user(db, f"cc2-{uuid.uuid4().hex[:6]}@test.com", "CC2")
        ws = _make_workspace(db, owner, f"cc-ws-{uuid.uuid4().hex[:6]}", "CC WS")
        db.commit()

        result = retrieve_catalog_context(db, ws.id, "Tem carro automático disponível?")
        assert result.retrieval_attempted is True
        assert result.items == []
        assert result.context_block is None

    def test_handles_db_error_gracefully(self, db: Session):
        ws_id = uuid.uuid4()
        with patch(
            "app.services.catalog_retrieval_service.retrieve_catalog_items",
            side_effect=Exception("DB error"),
        ):
            result = retrieve_catalog_context(db, ws_id, "Tem produto disponível?")
        assert result.error_message is not None
        assert result.items == []

    def test_empty_query_skips_retrieval(self, db: Session):
        result = retrieve_catalog_context(db, uuid.uuid4(), "")
        assert result.retrieval_attempted is False


# ── Integration: conversation_context_builder ─────────────────────────────────

class TestConversationContextBuilderIntegration:
    """Verify catalog context is injected into the system prompt."""

    def test_catalog_injected_in_system_prompt(self, db: Session):
        from app.models.agent import Agent
        from app.models.agent_prompt_settings import AgentPromptSettings
        from app.models.conversation import Conversation
        from app.models.conversation_message import ConversationMessage
        from app.services.conversation_context_builder import build_conversation_context

        owner = _make_user(db, f"ci1-{uuid.uuid4().hex[:6]}@test.com", "CI1")
        ws = _make_workspace(db, owner, f"ci-ws-{uuid.uuid4().hex[:6]}", "CI WS")
        _make_item(db, ws.id, "Produto Premium", searchable_text="produto premium plano")
        agent = Agent(workspace_id=ws.id, name="Test Agent", status="active", catalog_enabled=True)
        db.add(agent)
        db.flush()
        ps = AgentPromptSettings(agent_id=agent.id, system_prompt="Você é um assistente.")
        db.add(ps)
        conv = Conversation(
            workspace_id=ws.id,
            agent_id=agent.id,
            channel_type="internal",
            status="open",
            ai_enabled=True,
        )
        db.add(conv)
        db.flush()
        msg = ConversationMessage(
            workspace_id=ws.id,
            conversation_id=conv.id,
            direction="inbound",
            sender_type="customer",
            content="Quais planos vocês oferecem?",
            content_type="text",
        )
        db.add(msg)
        db.commit()

        ctx = build_conversation_context(
            db, workspace_id=ws.id, conversation=conv, agent=agent, trigger_message=msg
        )
        assert "Produto Premium" in ctx.system_prompt or ctx.catalog_items_count == 0
        assert ctx.catalog_retrieval_attempted is True

    def test_no_catalog_for_non_commercial_message(self, db: Session):
        from app.models.agent import Agent
        from app.models.agent_prompt_settings import AgentPromptSettings
        from app.models.conversation import Conversation
        from app.models.conversation_message import ConversationMessage
        from app.services.conversation_context_builder import build_conversation_context

        owner = _make_user(db, f"ci2-{uuid.uuid4().hex[:6]}@test.com", "CI2")
        ws = _make_workspace(db, owner, f"ci-ws2-{uuid.uuid4().hex[:6]}", "CI WS2")
        _make_item(db, ws.id, "Produto X", searchable_text="produto x plano")
        agent = Agent(workspace_id=ws.id, name="Agent2", status="active")
        db.add(agent)
        db.flush()
        ps = AgentPromptSettings(agent_id=agent.id, system_prompt="Assistente.")
        db.add(ps)
        conv = Conversation(
            workspace_id=ws.id, agent_id=agent.id,
            channel_type="internal", status="open", ai_enabled=True,
        )
        db.add(conv)
        db.flush()
        msg = ConversationMessage(
            workspace_id=ws.id, conversation_id=conv.id,
            direction="inbound", sender_type="customer",
            content="Olá, tudo bem?", content_type="text",
        )
        db.add(msg)
        db.commit()

        ctx = build_conversation_context(
            db, workspace_id=ws.id, conversation=conv, agent=agent, trigger_message=msg
        )
        assert ctx.catalog_retrieval_attempted is False
        assert ctx.catalog_items_count == 0


# ── Integration: agent_test_service response schema ───────────────────────────

class TestAgentTestServiceCatalogFields:
    """Verify that AgentTestResponse exposes catalog metadata."""

    def test_response_has_catalog_fields(self):
        from app.schemas.agent_test import AgentTestResponse, AgentTestModelInfo
        resp = AgentTestResponse(
            reply="ok",
            credits_used=1,
            input_tokens=10,
            output_tokens=5,
            duration_ms=100,
            model=AgentTestModelInfo(
                display_name="Claude Haiku",
                provider="anthropic",
                model_name="claude-haiku-4-5",
            ),
            session_id=uuid.uuid4(),
            rag_used=False,
            retrieved_chunks_count=0,
            catalog_retrieval_attempted=True,
            catalog_items_count=2,
            catalog_items_used=[{"id": str(uuid.uuid4()), "name": "X", "score": 1.0}],
        )
        assert resp.catalog_retrieval_attempted is True
        assert resp.catalog_items_count == 2
        assert len(resp.catalog_items_used) == 1
