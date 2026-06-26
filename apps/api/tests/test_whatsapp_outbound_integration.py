"""
Integration tests for WhatsApp outbound delivery — Phase 6.3-A.

Tests the hook in ConversationMessageService that calls
whatsapp_outbound_service.deliver_human_message() after saving
outbound/human messages in WhatsApp conversations.

All Meta HTTP calls are mocked — no real network requests.
"""

import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.agent import Agent
from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.conversation_message import ConversationMessageCreate
from app.services.conversation_message_service import create_message
from tests.conftest import _make_user

# ── Helpers ────────────────────────────────────────────────────────────────────


def _seed_member(db: Session, workspace: Workspace, email: str, name: str) -> User:
    user = _make_user(db, email, name)
    db.add(WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=MemberRole.member,
        status=MemberStatus.active,
    ))
    db.flush()
    return user


def _seed_agent(db: Session, workspace: Workspace) -> Agent:
    a = Agent(workspace_id=workspace.id, name=f"Agent-{uuid.uuid4().hex[:6]}")
    db.add(a)
    db.flush()
    return a


def _seed_contact(
    db: Session,
    workspace: Workspace,
    phone: str = "+5537888000001",
    external_id: str = "whatsapp:5537888000001",
) -> Contact:
    c = Contact(
        workspace_id=workspace.id,
        name="WA Contact",
        phone=phone,
        external_id=external_id,
    )
    db.add(c)
    db.flush()
    return c


def _seed_whatsapp_channel(
    db: Session,
    workspace: Workspace,
    agent: Agent,
    phone_number_id: str = "PID_INTEG_TEST",
    access_token_ref: str = "env:WHATSAPP_TEMP_ACCESS_TOKEN",
) -> Channel:
    ch = Channel(
        workspace_id=workspace.id,
        agent_id=agent.id,
        channel_type="whatsapp",
        name="WA Integ",
        public_key=f"wap_{uuid.uuid4().hex[:20]}",
        status="active",
        config_json={
            "provider": "meta_cloud_api",
            "onboarding_type": "manual",
            "waba_id": "WABA_TEST",
            "phone_number_id": phone_number_id,
            "display_phone_number": "+1 555 000 0000",
            "business_id": None,
            "access_token_ref": access_token_ref,
            "status": "testing",
            "connected_at": None,
            "last_webhook_at": None,
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.flush()
    return ch


def _seed_whatsapp_conversation(
    db: Session,
    workspace: Workspace,
    contact: Contact,
    agent: Agent,
    channel: Channel,
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        agent_id=agent.id,
        channel_id=channel.id,
        channel_type="whatsapp",
        status="open",
        ai_enabled=False,
    )
    db.add(conv)
    db.commit()
    return conv


def _seed_internal_conversation(
    db: Session,
    workspace: Workspace,
    contact: Contact,
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        channel_type="internal",
        status="open",
        ai_enabled=False,
    )
    db.add(conv)
    db.commit()
    return conv


def _seed_widget_conversation(
    db: Session,
    workspace: Workspace,
    contact: Contact,
    agent: Agent,
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        agent_id=agent.id,
        channel_type="web_widget",
        status="open",
        ai_enabled=False,
    )
    db.add(conv)
    db.commit()
    return conv


def _make_human_outbound_data() -> ConversationMessageCreate:
    return ConversationMessageCreate(
        content="Olá, como posso ajudar?",
        direction="outbound",
        sender_type="human",
    )


def _make_customer_inbound_data() -> ConversationMessageCreate:
    return ConversationMessageCreate(
        content="Preciso de ajuda",
        direction="inbound",
        sender_type="customer",
    )


def _make_agent_outbound_data() -> ConversationMessageCreate:
    return ConversationMessageCreate(
        content="Mensagem do agente",
        direction="outbound",
        sender_type="agent",
    )


def _make_human_internal_data() -> ConversationMessageCreate:
    return ConversationMessageCreate(
        content="Nota interna",
        direction="internal",
        sender_type="human",
    )


def _meta_success(wamid: str = "wamid.INTEG001") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"messages": [{"id": wamid}]}
    resp.raise_for_status.return_value = None
    return resp


# ── WhatsApp outbound delivery triggered ──────────────────────────────────────


class TestWhatsAppDeliveryTriggered:
    def test_outbound_human_in_whatsapp_conv_calls_delivery(
        self, db: Session, workspace_a: Workspace, monkeypatch
    ):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_test_abc")
        user = _seed_member(db, workspace_a, "op1@test.com", "Op 1")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a)
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        with patch("httpx.post", return_value=_meta_success()) as mock_post:
            create_message(db, workspace_a.id, conv.id, user.id, _make_human_outbound_data())

        mock_post.assert_called_once()

    def test_outbound_human_success_saves_external_message_id(
        self, db: Session, workspace_a: Workspace, monkeypatch
    ):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_test_abc")
        user = _seed_member(db, workspace_a, "op2@test.com", "Op 2")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a, external_id="whatsapp:5537000000002")
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        with patch("httpx.post", return_value=_meta_success("wamid.SAVED_001")):
            msg = create_message(
                db, workspace_a.id, conv.id, user.id, _make_human_outbound_data()
            )

        db.refresh(msg)
        assert msg.external_message_id == "wamid.SAVED_001"

    def test_message_saved_even_if_delivery_fails(
        self, db: Session, workspace_a: Workspace, monkeypatch
    ):
        monkeypatch.delenv("WHATSAPP_TEMP_ACCESS_TOKEN", raising=False)
        user = _seed_member(db, workspace_a, "op3@test.com", "Op 3")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a, external_id="whatsapp:5537000000003")
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        msg = create_message(
            db, workspace_a.id, conv.id, user.id, _make_human_outbound_data()
        )

        # Message must exist regardless of delivery outcome.
        assert msg.id is not None
        assert msg.direction == "outbound"
        assert msg.sender_type == "human"

    def test_message_saved_even_if_delivery_raises_exception(
        self, db: Session, workspace_a: Workspace, monkeypatch
    ):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_test_abc")
        user = _seed_member(db, workspace_a, "op4@test.com", "Op 4")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a, external_id="whatsapp:5537000000004")
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        with patch(
            "app.services.whatsapp_outbound_service.deliver_human_message",
            side_effect=RuntimeError("unexpected boom"),
        ):
            msg = create_message(
                db, workspace_a.id, conv.id, user.id, _make_human_outbound_data()
            )

        assert msg.id is not None


# ── WhatsApp outbound delivery NOT triggered ──────────────────────────────────


class TestWhatsAppDeliveryNotTriggered:
    def test_outbound_human_in_web_widget_conv_does_not_call_delivery(
        self, db: Session, workspace_a: Workspace
    ):
        user = _seed_member(db, workspace_a, "op5@test.com", "Op 5")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a, external_id=None, phone=None)
        conv = _seed_widget_conversation(db, workspace_a, contact, agent)

        with patch("httpx.post") as mock_post:
            create_message(db, workspace_a.id, conv.id, user.id, _make_human_outbound_data())

        mock_post.assert_not_called()

    def test_outbound_agent_in_whatsapp_conv_does_not_call_delivery(
        self, db: Session, workspace_a: Workspace, monkeypatch
    ):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_test_abc")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a, external_id="whatsapp:5537000000005")
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        with patch("httpx.post") as mock_post:
            # sender_type=agent: delivery must not trigger
            create_message(
                db, workspace_a.id, conv.id, None, _make_agent_outbound_data()
            )

        mock_post.assert_not_called()

    def test_inbound_customer_in_whatsapp_conv_does_not_call_delivery(
        self, db: Session, workspace_a: Workspace, monkeypatch
    ):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_test_abc")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a, external_id="whatsapp:5537000000006")
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        with patch("httpx.post") as mock_post:
            create_message(
                db, workspace_a.id, conv.id, None, _make_customer_inbound_data()
            )

        mock_post.assert_not_called()

    def test_internal_human_in_whatsapp_conv_does_not_call_delivery(
        self, db: Session, workspace_a: Workspace, monkeypatch
    ):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_test_abc")
        user = _seed_member(db, workspace_a, "op6@test.com", "Op 6")
        agent = _seed_agent(db, workspace_a)
        contact = _seed_contact(db, workspace_a, external_id="whatsapp:5537000000007")
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        with patch("httpx.post") as mock_post:
            create_message(
                db, workspace_a.id, conv.id, user.id, _make_human_internal_data()
            )

        mock_post.assert_not_called()

    def test_outbound_human_in_internal_conv_does_not_call_delivery(
        self, db: Session, workspace_a: Workspace
    ):
        user = _seed_member(db, workspace_a, "op7@test.com", "Op 7")
        contact = _seed_contact(db, workspace_a, external_id=None, phone=None)
        conv = _seed_internal_conversation(db, workspace_a, contact)

        with patch("httpx.post") as mock_post:
            create_message(db, workspace_a.id, conv.id, user.id, _make_human_outbound_data())

        mock_post.assert_not_called()


# ── channel_id persisted by inbound service ───────────────────────────────────


class TestConversationChannelId:
    def test_channel_id_persists_in_conversation(self, db: Session, workspace_a: Workspace):
        agent = _seed_agent(db, workspace_a)
        channel = _seed_whatsapp_channel(db, workspace_a, agent)
        contact = _seed_contact(db, workspace_a)
        conv = _seed_whatsapp_conversation(db, workspace_a, contact, agent, channel)

        db.refresh(conv)
        assert conv.channel_id == channel.id

    def test_channel_id_nullable_for_non_whatsapp(self, db: Session, workspace_a: Workspace):
        contact = _seed_contact(db, workspace_a, external_id=None, phone=None)
        conv = _seed_internal_conversation(db, workspace_a, contact)

        db.refresh(conv)
        assert conv.channel_id is None
