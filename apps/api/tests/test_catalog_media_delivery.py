"""
Tests for Catálogo.6 — Catalog Media Delivery Service.

Coverage:
- decide: not whatsapp → skip
- decide: no catalog retrieval → skip
- decide: multiple items → skip
- decide: no items → skip
- decide: score too low → skip
- decide: item not active → skip
- decide: no primary image → skip
- decide: local storage (file://) → skip
- decide: storage URL generation fails → skip
- decide: recently sent (anti-spam) → skip
- decide: eligible → should_send=True with correct fields
- decide: caption with price
- decide: caption without price
- deliver: sends image, creates ConversationMessage with sent=True
- deliver: WhatsApp API failure → message created with sent=False
- deliver: missing wamid → message created with sent=False
- deliver: decision.should_send=False → returns None
- integration: text delivery failure prevents media delivery in reply service
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.catalog_item import CatalogItem
from app.models.catalog_media import CatalogMedia
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.catalog_media_delivery_service import (
    MediaDeliveryDecision,
    _build_caption,
    _was_recently_sent,
    decide_catalog_media_delivery,
    deliver_catalog_media_image,
)
from app.services.catalog_retrieval_service import CatalogRetrievalItem
from tests.conftest import _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_retrieval_item(
    item_id: uuid.UUID | None = None,
    score: float = 0.85,
    primary_media_available: bool = True,
    name: str = "Item Teste",
    price: float | None = 49900.0,
) -> CatalogRetrievalItem:
    return CatalogRetrievalItem(
        id=item_id or uuid.uuid4(),
        name=name,
        category_name=None,
        short_description=None,
        price=price,
        currency="BRL",
        tags=[],
        metadata_json={},
        primary_media_available=primary_media_available,
        score=score,
    )


def _make_conversation(
    db: Session, channel_type: str = "whatsapp", workspace_id: uuid.UUID | None = None
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace_id or uuid.uuid4(),
        agent_id=None,
        status="open",
        channel_type=channel_type,
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


def _make_agent_in_db(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Test Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _mock_storage(url: str = "https://cdn.example.com/img.jpg") -> MagicMock:
    s = MagicMock()
    s.generate_presigned_url.return_value = url
    return s


def _make_catalog_item_in_db(
    db: Session,
    workspace_id: uuid.UUID,
    status: str = "active",
) -> CatalogItem:
    item = CatalogItem(
        workspace_id=workspace_id,
        name="Corolla XEI 2021",
        status=status,
        currency="BRL",
        tags=[],
        metadata_json={},
        searchable_text="corolla xei automático",
        is_featured=False,
    )
    db.add(item)
    db.flush()
    return item


def _make_catalog_media_in_db(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    file_type: str = "image",
    is_primary: bool = True,
) -> CatalogMedia:
    media = CatalogMedia(
        workspace_id=workspace_id,
        item_id=item_id,
        file_key=f"catalog/{workspace_id}/{item_id}/img.jpg",
        original_filename="img.jpg",
        mime_type="image/jpeg",
        file_type=file_type,
        size_bytes=102400,
        is_primary=is_primary,
        sort_order=0,
        metadata_json={},
    )
    db.add(media)
    db.flush()
    return media


# ── decide_catalog_media_delivery ─────────────────────────────────────────────

class TestDecideCatalogMediaDelivery:
    def _run(self, db, workspace_id, conv, items, attempted=True, url="https://cdn.example.com/img.jpg"):
        storage = _mock_storage(url)
        text_msg = SimpleNamespace(id=uuid.uuid4(), metadata_json={})
        return decide_catalog_media_delivery(
            db=db,
            workspace_id=workspace_id,
            conversation=conv,
            catalog_items=items,
            catalog_retrieval_attempted=attempted,
            storage=storage,
            text_message=text_msg,
        )

    def test_not_whatsapp(self, db: Session):
        owner = _make_user(db, f"d1-{uuid.uuid4().hex[:6]}@t.com", "D1")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, channel_type="web_widget", workspace_id=ws.id)
        result = self._run(db, ws.id, conv, [_make_retrieval_item()])
        assert result.should_send is False
        assert result.reason == "not_whatsapp"

    def test_no_catalog_retrieval(self, db: Session):
        owner = _make_user(db, f"d2-{uuid.uuid4().hex[:6]}@t.com", "D2")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        result = self._run(db, ws.id, conv, [], attempted=False)
        assert result.should_send is False
        assert result.reason == "no_catalog_retrieval"

    def test_multiple_items(self, db: Session):
        owner = _make_user(db, f"d3-{uuid.uuid4().hex[:6]}@t.com", "D3")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        items = [_make_retrieval_item(), _make_retrieval_item()]
        result = self._run(db, ws.id, conv, items)
        assert result.should_send is False
        assert result.reason == "multiple_catalog_items"

    def test_no_items(self, db: Session):
        owner = _make_user(db, f"d4-{uuid.uuid4().hex[:6]}@t.com", "D4")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        result = self._run(db, ws.id, conv, [])
        assert result.should_send is False
        assert result.reason == "no_catalog_items"

    def test_score_too_low(self, db: Session):
        owner = _make_user(db, f"d5-{uuid.uuid4().hex[:6]}@t.com", "D5")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        item = _make_retrieval_item(score=0.30)
        result = self._run(db, ws.id, conv, [item])
        assert result.should_send is False
        assert "score_too_low" in result.reason

    def test_no_primary_media_flag(self, db: Session):
        owner = _make_user(db, f"d6-{uuid.uuid4().hex[:6]}@t.com", "D6")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        item = _make_retrieval_item(primary_media_available=False)
        result = self._run(db, ws.id, conv, [item])
        assert result.should_send is False
        assert result.reason == "no_primary_media"

    def test_item_not_active(self, db: Session):
        owner = _make_user(db, f"d7-{uuid.uuid4().hex[:6]}@t.com", "D7")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        db_item = _make_catalog_item_in_db(db, ws.id, status="inactive")
        db.commit()
        ri = _make_retrieval_item(item_id=db_item.id)
        result = self._run(db, ws.id, conv, [ri])
        assert result.should_send is False
        assert result.reason == "item_not_active"

    def test_no_primary_image_in_db(self, db: Session):
        owner = _make_user(db, f"d8-{uuid.uuid4().hex[:6]}@t.com", "D8")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        db_item = _make_catalog_item_in_db(db, ws.id)
        db.commit()
        ri = _make_retrieval_item(item_id=db_item.id)
        result = self._run(db, ws.id, conv, [ri])
        assert result.should_send is False
        assert result.reason == "primary_image_not_found"

    def test_file_url_not_public(self, db: Session):
        owner = _make_user(db, f"d9-{uuid.uuid4().hex[:6]}@t.com", "D9")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        db_item = _make_catalog_item_in_db(db, ws.id)
        _make_catalog_media_in_db(db, ws.id, db_item.id)
        db.commit()
        ri = _make_retrieval_item(item_id=db_item.id)
        result = self._run(db, ws.id, conv, [ri], url="file:///tmp/img.jpg")
        assert result.should_send is False
        assert result.reason == "media_url_not_public"

    def test_storage_url_generation_fails(self, db: Session):
        owner = _make_user(db, f"d10-{uuid.uuid4().hex[:6]}@t.com", "D10")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        db_item = _make_catalog_item_in_db(db, ws.id)
        _make_catalog_media_in_db(db, ws.id, db_item.id)
        db.commit()
        ri = _make_retrieval_item(item_id=db_item.id)

        storage = MagicMock()
        storage.generate_presigned_url.side_effect = Exception("storage down")
        text_msg = SimpleNamespace(id=uuid.uuid4(), metadata_json={})
        result = decide_catalog_media_delivery(
            db=db, workspace_id=ws.id, conversation=conv,
            catalog_items=[ri], catalog_retrieval_attempted=True,
            storage=storage, text_message=text_msg,
        )
        assert result.should_send is False
        assert result.reason == "media_url_generation_failed"

    def test_eligible_returns_should_send_true(self, db: Session):
        owner = _make_user(db, f"d11-{uuid.uuid4().hex[:6]}@t.com", "D11")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        db_item = _make_catalog_item_in_db(db, ws.id)
        media = _make_catalog_media_in_db(db, ws.id, db_item.id)
        db.commit()
        ri = _make_retrieval_item(item_id=db_item.id, name="Corolla XEI 2021", price=88900.0)
        result = self._run(db, ws.id, conv, [ri])
        assert result.should_send is True
        assert result.item_id == db_item.id
        assert result.media_id == media.id
        assert result.media_url == "https://cdn.example.com/img.jpg"
        assert result.reason == "single_recommended_item_with_primary_image"

    def test_anti_spam_blocks_repeated_send(self, db: Session):
        owner = _make_user(db, f"d12-{uuid.uuid4().hex[:6]}@t.com", "D12")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        db_item = _make_catalog_item_in_db(db, ws.id)
        media = _make_catalog_media_in_db(db, ws.id, db_item.id)
        agent = _make_agent_in_db(db, ws.id)
        db.commit()

        # Simulate a prior sent message with this media_id — "sent" now lives
        # on the provider-agnostic "delivery" block, not catalog_media_delivery.
        prior_msg = ConversationMessage(
            workspace_id=ws.id,
            conversation_id=conv.id,
            direction="outbound",
            sender_type="agent",
            agent_id=agent.id,
            content="[Imagem]",
            content_type="image",
            metadata_json={
                "catalog_media_delivery": {"media_id": str(media.id)},
                "delivery": {"status": "sent"},
            },
        )
        db.add(prior_msg)
        db.commit()

        ri = _make_retrieval_item(item_id=db_item.id)
        result = self._run(db, ws.id, conv, [ri])
        assert result.should_send is False
        assert result.reason == "recently_sent"


# ── Caption ───────────────────────────────────────────────────────────────────

class TestBuildCaption:
    def test_caption_with_price(self):
        item = _make_retrieval_item(name="Toyota Corolla XEI 2021", price=88900.0)
        caption = _build_caption(item)
        assert "Toyota Corolla XEI 2021" in caption
        assert "88.900" in caption

    def test_caption_without_price(self):
        item = _make_retrieval_item(name="Produto Sem Preço", price=None)
        caption = _build_caption(item)
        assert caption == "Produto Sem Preço"


# ── deliver_catalog_media_image ───────────────────────────────────────────────

class TestDeliverCatalogMediaImage:
    def _make_decision(self, item_id=None, media_id=None) -> MediaDeliveryDecision:
        return MediaDeliveryDecision(
            should_send=True,
            reason="single_recommended_item_with_primary_image",
            item_id=item_id or uuid.uuid4(),
            media_id=media_id or uuid.uuid4(),
            file_key="catalog-media/ws/img.jpg",
            mime_type="image/jpeg",
            media_url="https://cdn.example.com/img.jpg",
            caption="Toyota Corolla XEI 2021 — R$ 88.900,00",
        )

    @staticmethod
    def _fake_success(db, message, conversation, *, storage_key, mime_type, caption=None):
        existing = message.metadata_json or {}
        message.metadata_json = {**existing, "delivery": {"status": "sent", "wamid": "wamid.test123"}}
        db.commit()

    @staticmethod
    def _fake_failure(db, message, conversation, *, storage_key, mime_type, caption=None):
        existing = message.metadata_json or {}
        message.metadata_json = {**existing, "delivery": {"status": "failed", "error": "provider unavailable"}}
        db.commit()

    def test_sends_image_and_creates_message(self, db: Session):
        owner = _make_user(db, f"dv1-{uuid.uuid4().hex[:6]}@t.com", "DV1")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        agent = _make_agent_in_db(db, ws.id)
        db.commit()
        decision = self._make_decision()

        with patch(
            "app.services.messaging.deliver_media_message",
            side_effect=self._fake_success,
        ) as mock_deliver:
            msg = deliver_catalog_media_image(
                db=db,
                workspace_id=ws.id,
                conversation=conv,
                decision=decision,
                agent_id=agent.id,
            )

        assert msg is not None
        assert msg.content_type == "image"
        assert msg.media_url == decision.file_key
        mock_deliver.assert_called_once()
        _, kwargs = mock_deliver.call_args
        assert kwargs["storage_key"] == decision.file_key
        assert kwargs["mime_type"] == decision.mime_type
        assert msg.metadata_json["delivery"]["status"] == "sent"
        catalog_meta = msg.metadata_json["catalog_media_delivery"]
        assert catalog_meta["item_id"] == str(decision.item_id)
        assert catalog_meta["media_id"] == str(decision.media_id)

    def test_api_failure_creates_failed_message(self, db: Session):
        owner = _make_user(db, f"dv2-{uuid.uuid4().hex[:6]}@t.com", "DV2")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        agent = _make_agent_in_db(db, ws.id)
        db.commit()
        decision = self._make_decision()

        with patch(
            "app.services.messaging.deliver_media_message",
            side_effect=Exception("Provider unavailable"),
        ):
            msg = deliver_catalog_media_image(
                db=db,
                workspace_id=ws.id,
                conversation=conv,
                decision=decision,
                agent_id=agent.id,
            )

        assert msg is not None
        delivery = msg.metadata_json["catalog_media_delivery"]
        assert delivery["sent"] is False
        assert "Provider unavailable" in delivery["error"]

    def test_provider_records_failure_without_raising(self, db: Session):
        """A provider that handles its own errors (never raises) still leaves
        the message correctly marked as failed via its own delivery block."""
        owner = _make_user(db, f"dv3-{uuid.uuid4().hex[:6]}@t.com", "DV3")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        agent = _make_agent_in_db(db, ws.id)
        db.commit()
        decision = self._make_decision()

        with patch(
            "app.services.messaging.deliver_media_message",
            side_effect=self._fake_failure,
        ):
            msg = deliver_catalog_media_image(
                db=db,
                workspace_id=ws.id,
                conversation=conv,
                decision=decision,
                agent_id=agent.id,
            )

        assert msg is not None
        assert msg.metadata_json["delivery"]["status"] == "failed"

    def test_should_send_false_returns_none(self, db: Session):
        owner = _make_user(db, f"dv4-{uuid.uuid4().hex[:6]}@t.com", "DV4")
        ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        conv = _make_conversation(db, workspace_id=ws.id)
        agent = _make_agent_in_db(db, ws.id)
        db.commit()
        decision = MediaDeliveryDecision(
            should_send=False, reason="multiple_catalog_items"
        )
        msg = deliver_catalog_media_image(
            db=db,
            workspace_id=ws.id,
            conversation=conv,
            decision=decision,
            agent_id=agent.id,
        )
        assert msg is None


# ── Anti-spam helper ──────────────────────────────────────────────────────────

class TestWasRecentlySent:
    def test_not_recently_sent_when_no_messages(self, db: Session):
        owner = _make_user(db, f"ws1-{uuid.uuid4().hex[:6]}@t.com", "WS1")
        _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "W")
        db.commit()
        conv_id = uuid.uuid4()
        assert _was_recently_sent(db, conv_id, str(uuid.uuid4())) is False
