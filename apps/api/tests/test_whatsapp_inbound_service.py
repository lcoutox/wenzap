"""
Tests for whatsapp_inbound_service.py — Phase 6.2-A / WhatsApp AI.1.

Covers:
  Contact
  - creates new contact by wa_id
  - reuses existing contact with same wa_id in same workspace
  - updates contact name when it was set to wa_id and profile_name is now known
  - does not mix contacts between workspaces

  Conversation
  - channel with auto_reply_enabled=False creates conversation with ai_enabled=False
  - channel with auto_reply_enabled=True creates conversation with ai_enabled=True
  - existing conversation preserves ai_enabled (not overridden on subsequent messages)
  - reuses open conversation for same contact/channel/agent
  - reuses pending conversation
  - creates new conversation if previous was resolved
  - creates new conversation if previous was archived
  - agent_id comes from the channel

  Auto-reply
  - channel with auto_reply_enabled=True dispatches agent reply for new messages
  - duplicate wamid does not dispatch agent reply twice
  - existing conversation with ai_enabled=False does not dispatch agent reply

  Message
  - creates inbound/customer message with correct fields
  - content is text_body
  - external_message_id is set to wamid
  - metadata_json contains whatsapp_timestamp and wa_id
  - second call with same wamid does not create duplicate
  - conversation.last_message_at is updated

  Channel
  - channel not found returns None without raising
  - archived channel returns None (get_whatsapp_channel_by_phone_number_id contract)
"""

import uuid
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.user import User
from app.models.workspace import Workspace
from app.services.whatsapp_inbound_service import process_inbound_message
from app.services.whatsapp_webhook_parser import WhatsAppContact, WhatsAppInboundMessage

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="WA Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_whatsapp_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    phone_number_id: str = "PHONE_ID_001",
    status: str = "active",
    auto_reply_enabled: bool = False,
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="WhatsApp Test",
        public_key=f"wap_{uuid.uuid4().hex[:24]}",
        status=status,
        config_json={
            "provider": "meta_cloud_api",
            "onboarding_type": "manual",
            "waba_id": "9999000011112222",
            "phone_number_id": phone_number_id,
            "display_phone_number": None,
            "business_id": None,
            "access_token_ref": None,
            "status": "testing",
            "connected_at": None,
            "last_webhook_at": None,
            "auto_reply_enabled": auto_reply_enabled,
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _make_msg(
    phone_number_id: str = "PHONE_ID_001",
    wa_id: str = "5537111111111",
    wamid: str = "wamid.TEST001",
    text_body: str = "Olá",
    profile_name: str | None = "Lucas",
    timestamp: int = 1710000000,
) -> WhatsAppInboundMessage:
    return WhatsAppInboundMessage(
        phone_number_id=phone_number_id,
        wamid=wamid,
        from_wa_id=wa_id,
        timestamp=timestamp,
        text_body=text_body,
        contact=WhatsAppContact(wa_id=wa_id, profile_name=profile_name),
    )


def _make_existing_contact(
    db: Session,
    workspace_id: uuid.UUID,
    wa_id: str,
    name: str | None = None,
) -> Contact:
    contact = Contact(
        workspace_id=workspace_id,
        name=name or wa_id,
        phone=f"+{wa_id}",
        external_id=f"whatsapp:{wa_id}",
        metadata_json={"source": "whatsapp", "whatsapp": {"wa_id": wa_id}},
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def _make_existing_conversation(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    agent_id: uuid.UUID | None,
    status: str = "open",
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace_id,
        contact_id=contact_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        status=status,
        ai_enabled=False,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


# ── Contact ────────────────────────────────────────────────────────────────────


class TestContactCreation:
    def test_creates_new_contact_by_wa_id(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        msg = _make_msg(wa_id="5537222222222")

        process_inbound_message(db, msg)

        contact = db.scalar(
            select(Contact).where(
                Contact.workspace_id == workspace_a.id,
                Contact.external_id == "whatsapp:5537222222222",
            )
        )
        assert contact is not None
        assert contact.phone == "+5537222222222"

    def test_contact_name_set_to_profile_name(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        msg = _make_msg(wa_id="5537333333333", profile_name="Maria Silva")

        process_inbound_message(db, msg)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == "whatsapp:5537333333333")
        )
        assert contact is not None
        assert contact.name == "Maria Silva"

    def test_contact_name_falls_back_to_wa_id_when_no_profile(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        msg = _make_msg(wa_id="5537444444444", profile_name=None)

        process_inbound_message(db, msg)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == "whatsapp:5537444444444")
        )
        assert contact is not None
        assert contact.name == "5537444444444"

    def test_reuses_existing_contact_with_same_wa_id(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wa_id = "5537555555555"
        existing = _make_existing_contact(db, workspace_a.id, wa_id, name="João")

        process_inbound_message(db, _make_msg(wa_id=wa_id, profile_name="João"))
        process_inbound_message(db, _make_msg(wa_id=wa_id, wamid="wamid.MSG2", profile_name="João"))

        contacts = list(
            db.scalars(
                select(Contact).where(
                    Contact.workspace_id == workspace_a.id,
                    Contact.external_id == f"whatsapp:{wa_id}",
                )
            ).all()
        )
        assert len(contacts) == 1
        assert contacts[0].id == existing.id

    def test_updates_name_when_it_was_wa_id_and_profile_name_arrives(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wa_id = "5537666666666"
        # Create contact with name = wa_id (default fallback)
        _make_existing_contact(db, workspace_a.id, wa_id, name=wa_id)

        msg = _make_msg(wa_id=wa_id, profile_name="Clara Costa", wamid="wamid.UPDATE1")
        process_inbound_message(db, msg)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == f"whatsapp:{wa_id}")
        )
        assert contact is not None
        assert contact.name == "Clara Costa"

    def test_does_not_update_name_when_already_has_real_name(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wa_id = "5537777777777"
        _make_existing_contact(db, workspace_a.id, wa_id, name="Pedro Alves")

        msg = _make_msg(wa_id=wa_id, profile_name="Outro Nome", wamid="wamid.NOUPDATE")
        process_inbound_message(db, msg)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == f"whatsapp:{wa_id}")
        )
        # Name should not change because it was already a real name (not the wa_id fallback)
        assert contact is not None
        assert contact.name == "Pedro Alves"

    def test_does_not_mix_contacts_between_workspaces(
        self, db: Session, workspace_a: Workspace, workspace_b: Workspace
    ):
        agent_a = _make_agent(db, workspace_a.id)
        agent_b = _make_agent(db, workspace_b.id)
        _make_whatsapp_channel(db, workspace_a.id, agent_a.id, phone_number_id="PID_WS_A")
        _make_whatsapp_channel(db, workspace_b.id, agent_b.id, phone_number_id="PID_WS_B")

        wa_id = "5537888888888"
        process_inbound_message(
            db, _make_msg(phone_number_id="PID_WS_A", wa_id=wa_id, wamid="wamid.WS_A")
        )
        process_inbound_message(
            db, _make_msg(phone_number_id="PID_WS_B", wa_id=wa_id, wamid="wamid.WS_B")
        )

        contacts_a = list(
            db.scalars(
                select(Contact).where(
                    Contact.workspace_id == workspace_a.id,
                    Contact.external_id == f"whatsapp:{wa_id}",
                )
            ).all()
        )
        contacts_b = list(
            db.scalars(
                select(Contact).where(
                    Contact.workspace_id == workspace_b.id,
                    Contact.external_id == f"whatsapp:{wa_id}",
                )
            ).all()
        )
        assert len(contacts_a) == 1
        assert len(contacts_b) == 1
        assert contacts_a[0].id != contacts_b[0].id

    def test_contact_metadata_contains_whatsapp_source(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        msg = _make_msg(wa_id="5537900000001", profile_name="Test User")

        process_inbound_message(db, msg)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == "whatsapp:5537900000001")
        )
        assert contact is not None
        assert contact.metadata_json is not None
        assert contact.metadata_json["source"] == "whatsapp"
        assert contact.metadata_json["whatsapp"]["wa_id"] == "5537900000001"
        assert contact.metadata_json["whatsapp"]["profile_name"] == "Test User"


# ── Conversation ───────────────────────────────────────────────────────────────


class TestConversationCreation:
    def test_creates_conversation_with_whatsapp_channel_type(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg())

        conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
        assert conv is not None
        assert conv.channel_type == "whatsapp"

    def test_creates_conversation_with_ai_enabled_false(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg())

        conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
        assert conv is not None
        assert conv.ai_enabled is False

    def test_creates_conversation_with_status_open(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg())

        conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
        assert conv is not None
        assert conv.status == "open"

    def test_agent_id_comes_from_channel(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg())

        conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
        assert conv is not None
        assert conv.agent_id == agent.id

    def test_reuses_open_conversation_for_same_contact(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wa_id = "5537100000001"
        existing_contact = _make_existing_contact(db, workspace_a.id, wa_id)
        existing_conv = _make_existing_conversation(
            db, workspace_a.id, existing_contact.id, agent.id, status="open"
        )

        process_inbound_message(db, _make_msg(wa_id=wa_id, wamid="wamid.REUSE1"))

        all_convs = list(
            db.scalars(
                select(Conversation).where(Conversation.workspace_id == workspace_a.id)
            ).all()
        )
        assert len(all_convs) == 1
        assert all_convs[0].id == existing_conv.id

    def test_reuses_pending_conversation(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wa_id = "5537100000002"
        contact = _make_existing_contact(db, workspace_a.id, wa_id)
        existing_conv = _make_existing_conversation(
            db, workspace_a.id, contact.id, agent.id, status="pending"
        )

        process_inbound_message(db, _make_msg(wa_id=wa_id, wamid="wamid.PENDING1"))

        all_convs = list(
            db.scalars(
                select(Conversation).where(Conversation.workspace_id == workspace_a.id)
            ).all()
        )
        assert len(all_convs) == 1
        assert all_convs[0].id == existing_conv.id

    def test_creates_new_conversation_if_previous_was_resolved(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wa_id = "5537100000003"
        contact = _make_existing_contact(db, workspace_a.id, wa_id)
        old_conv = _make_existing_conversation(
            db, workspace_a.id, contact.id, agent.id, status="resolved"
        )

        process_inbound_message(db, _make_msg(wa_id=wa_id, wamid="wamid.RESOLVED1"))

        all_convs = list(
            db.scalars(
                select(Conversation).where(Conversation.workspace_id == workspace_a.id)
            ).all()
        )
        assert len(all_convs) == 2
        new_conv_ids = {c.id for c in all_convs} - {old_conv.id}
        new_conv = db.get(Conversation, next(iter(new_conv_ids)))
        assert new_conv is not None
        assert new_conv.status == "open"

    def test_creates_new_conversation_if_previous_was_archived(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wa_id = "5537100000004"
        contact = _make_existing_contact(db, workspace_a.id, wa_id)
        _make_existing_conversation(
            db, workspace_a.id, contact.id, agent.id, status="archived"
        )

        process_inbound_message(db, _make_msg(wa_id=wa_id, wamid="wamid.ARCHIVED1"))

        all_convs = list(
            db.scalars(
                select(Conversation).where(Conversation.workspace_id == workspace_a.id)
            ).all()
        )
        assert len(all_convs) == 2


# ── Message ────────────────────────────────────────────────────────────────────


class TestMessageCreation:
    def test_creates_inbound_customer_message(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg(wamid="wamid.MSG_CREATE"))

        msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.workspace_id == workspace_a.id
            )
        )
        assert msg is not None
        assert msg.direction == "inbound"
        assert msg.sender_type == "customer"
        assert msg.content_type == "text"

    def test_message_content_is_text_body(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(
            db, _make_msg(text_body="Quero saber sobre planos", wamid="wamid.CONTENT")
        )

        msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.workspace_id == workspace_a.id
            )
        )
        assert msg is not None
        assert msg.content == "Quero saber sobre planos"

    def test_external_message_id_is_wamid(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg(wamid="wamid.UNIQUE_ID_XYZ"))

        msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.workspace_id == workspace_a.id
            )
        )
        assert msg is not None
        assert msg.external_message_id == "wamid.UNIQUE_ID_XYZ"

    def test_metadata_contains_timestamp_and_wa_id(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(
            db, _make_msg(wa_id="5537200000001", timestamp=1710000000, wamid="wamid.META1")
        )

        msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "wamid.META1"
            )
        )
        assert msg is not None
        assert msg.metadata_json is not None
        assert msg.metadata_json["whatsapp_timestamp"] == 1710000000
        assert msg.metadata_json["wa_id"] == "5537200000001"

    def test_duplicate_wamid_does_not_create_second_message(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)
        wamid = "wamid.DUPLICATE_TEST"

        process_inbound_message(db, _make_msg(wamid=wamid))
        process_inbound_message(db, _make_msg(wamid=wamid))

        messages = list(
            db.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.external_message_id == wamid
                )
            ).all()
        )
        assert len(messages) == 1

    def test_different_wamids_create_different_messages(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg(wamid="wamid.DIFF1", text_body="Primeira"))
        process_inbound_message(db, _make_msg(wamid="wamid.DIFF2", text_body="Segunda"))

        messages = list(
            db.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.workspace_id == workspace_a.id
                )
            ).all()
        )
        assert len(messages) == 2

    def test_conversation_last_message_at_updated(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        process_inbound_message(db, _make_msg(wamid="wamid.LMA1"))

        conv = db.scalar(
            select(Conversation).where(Conversation.workspace_id == workspace_a.id)
        )
        assert conv is not None
        assert conv.last_message_at is not None

    def test_process_returns_conversation_message(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        result = process_inbound_message(db, _make_msg(wamid="wamid.RETURN1"))

        assert result is not None
        assert isinstance(result, ConversationMessage)

    def test_process_returns_existing_on_duplicate_wamid(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        first = process_inbound_message(db, _make_msg(wamid="wamid.DUP_RETURN"))
        second = process_inbound_message(db, _make_msg(wamid="wamid.DUP_RETURN"))

        assert first is not None
        assert second is not None
        assert first.id == second.id


# ── Channel not found ──────────────────────────────────────────────────────────


class TestChannelNotFound:
    def test_unknown_phone_number_id_returns_none(
        self, db: Session, workspace_a: Workspace
    ):
        msg = _make_msg(phone_number_id="NONEXISTENT_PID")
        result = process_inbound_message(db, msg)
        assert result is None

    def test_unknown_phone_number_id_does_not_raise(
        self, db: Session, workspace_a: Workspace
    ):
        msg = _make_msg(phone_number_id="NONEXISTENT_PID_2")
        # Must not raise
        process_inbound_message(db, msg)

    def test_archived_channel_returns_none(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id, phone_number_id="ARCH_PID", status="archived"
        )
        result = process_inbound_message(db, _make_msg(phone_number_id="ARCH_PID"))
        assert result is None

    def test_no_contact_created_when_channel_not_found(
        self, db: Session, workspace_a: Workspace
    ):
        msg = _make_msg(phone_number_id="NO_CHANNEL_PID", wa_id="5537000000000")
        process_inbound_message(db, msg)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == "whatsapp:5537000000000")
        )
        assert contact is None


# ── Auto-reply (WhatsApp AI.1) ────────────────────────────────────────────────


class TestAutoReplyEnabled:
    """Tests for auto_reply_enabled channel config and AI reply triggering."""

    def test_auto_reply_disabled_creates_conversation_ai_disabled(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id,
            phone_number_id="AR_PID_OFF",
            auto_reply_enabled=False,
        )
        process_inbound_message(
            db, _make_msg(phone_number_id="AR_PID_OFF", wamid="wamid.AR_OFF_001")
        )

        conv = db.scalar(
            select(Conversation).where(
                Conversation.workspace_id == workspace_a.id,
                Conversation.channel_type == "whatsapp",
            )
        )
        assert conv is not None
        assert conv.ai_enabled is False

    def test_auto_reply_enabled_creates_conversation_ai_enabled(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id,
            phone_number_id="AR_PID_ON",
            auto_reply_enabled=True,
        )
        process_inbound_message(db, _make_msg(phone_number_id="AR_PID_ON", wamid="wamid.AR_ON_001"))

        conv = db.scalar(
            select(Conversation).where(
                Conversation.workspace_id == workspace_a.id,
                Conversation.channel_type == "whatsapp",
            )
        )
        assert conv is not None
        assert conv.ai_enabled is True

    def test_auto_reply_enabled_dispatches_agent_reply(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id,
            phone_number_id="AR_PID_DISPATCH",
            auto_reply_enabled=True,
        )

        with patch(
            "app.services.conversation_agent_reply_service.generate_conversation_agent_reply"
        ) as mock_reply:
            process_inbound_message(
                db, _make_msg(phone_number_id="AR_PID_DISPATCH", wamid="wamid.AR_DISPATCH_001")
            )

        mock_reply.assert_called_once()

    def test_duplicate_wamid_does_not_dispatch_agent_reply_twice(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id,
            phone_number_id="AR_PID_DUP",
            auto_reply_enabled=True,
        )
        msg = _make_msg(phone_number_id="AR_PID_DUP", wamid="wamid.AR_DUP_001")

        with patch(
            "app.services.conversation_agent_reply_service.generate_conversation_agent_reply"
        ) as mock_reply:
            process_inbound_message(db, msg)
            process_inbound_message(db, msg)  # duplicate

        mock_reply.assert_called_once()  # NOT twice

    def test_auto_reply_disabled_does_not_dispatch_agent_reply(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id,
            phone_number_id="AR_PID_NODISPATCH",
            auto_reply_enabled=False,
        )

        with patch(
            "app.services.conversation_agent_reply_service.generate_conversation_agent_reply"
        ) as mock_reply:
            process_inbound_message(
                db, _make_msg(phone_number_id="AR_PID_NODISPATCH", wamid="wamid.AR_ND_001")
            )

        mock_reply.assert_not_called()

    def test_human_takeover_preserves_ai_disabled(
        self, db: Session, workspace_a: Workspace, user_a: User
    ):
        """Human takeover (assigned_user_id set) prevents AI re-enabling on next message."""
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id,
            phone_number_id="AR_PID_TAKEOVER",
            auto_reply_enabled=True,
        )
        # First message creates conversation with ai_enabled=True.
        process_inbound_message(
            db, _make_msg(phone_number_id="AR_PID_TAKEOVER", wamid="wamid.AR_TKO_001")
        )

        # Human operator takes over (realistic state: both fields set together).
        conv = db.scalar(
            select(Conversation).where(
                Conversation.workspace_id == workspace_a.id,
                Conversation.channel_type == "whatsapp",
            )
        )
        assert conv is not None
        conv.ai_enabled = False
        conv.assigned_user_id = user_a.id
        db.commit()

        # Second message arrives — AI must NOT be re-enabled or triggered.
        with patch(
            "app.services.conversation_agent_reply_service.generate_conversation_agent_reply"
        ) as mock_reply:
            process_inbound_message(
                db, _make_msg(phone_number_id="AR_PID_TAKEOVER", wamid="wamid.AR_TKO_002")
            )

        mock_reply.assert_not_called()
        db.refresh(conv)
        assert conv.ai_enabled is False
        assert conv.assigned_user_id == user_a.id

    def test_existing_conversation_syncs_ai_enabled_when_channel_enables_auto_reply(
        self, db: Session, workspace_a: Workspace
    ):
        """
        Production scenario: conversation was created before auto_reply_enabled was
        toggled on, so it has ai_enabled=False and assigned_user_id=None.
        When a new message arrives and the channel now has auto_reply_enabled=True,
        the inbound service must sync ai_enabled=True and trigger the agent reply.
        """
        agent = _make_agent(db, workspace_a.id)
        # Channel starts with auto_reply_enabled=False.
        ch = _make_whatsapp_channel(
            db, workspace_a.id, agent.id,
            phone_number_id="AR_PID_SYNC",
            auto_reply_enabled=False,
        )
        # First message: conversation created with ai_enabled=False.
        process_inbound_message(
            db, _make_msg(phone_number_id="AR_PID_SYNC", wamid="wamid.AR_SYNC_001")
        )
        conv = db.scalar(
            select(Conversation).where(
                Conversation.workspace_id == workspace_a.id,
                Conversation.channel_type == "whatsapp",
            )
        )
        assert conv is not None
        assert conv.ai_enabled is False

        # Operator enables auto_reply on the channel.
        ch.config_json = {**ch.config_json, "auto_reply_enabled": True}
        db.commit()

        # Second message: inbound should sync ai_enabled=True and dispatch reply.
        with patch(
            "app.services.conversation_agent_reply_service.generate_conversation_agent_reply"
        ) as mock_reply:
            process_inbound_message(
                db, _make_msg(phone_number_id="AR_PID_SYNC", wamid="wamid.AR_SYNC_002")
            )

        mock_reply.assert_called_once()
        db.refresh(conv)
        assert conv.ai_enabled is True
