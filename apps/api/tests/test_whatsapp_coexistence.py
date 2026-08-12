"""
Tests for WhatsApp Coexistence — whatsapp-coexistence-prd.md.

Covers:
  Parsers (whatsapp_webhook_parser.py)
  - parse_history_messages: happy path, direction derivation, phase/progress
    metadata, missing required fields skipped, non-text placeholder
  - parse_state_sync_contacts: add/remove actions, missing phone skipped
  - parse_message_echoes: happy path, missing required fields skipped

  Service (whatsapp_coexistence_service.py)
  - process_history_message: creates contact/conversation/message, idempotent
    by wamid, does not touch the usage counter (no plan quota consumed),
    preserves original WhatsApp timestamp as created_at
  - process_state_sync_contact: add creates a Contact, remove is a no-op
  - process_message_echo: creates outbound/human message, pauses ai_enabled
    with handoff_reason, idempotent by wamid, unknown channel is a no-op
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.usage_counter import UsageCounter
from app.models.workspace import Workspace
from app.services.whatsapp_coexistence_service import (
    process_history_message,
    process_message_echo,
    process_state_sync_contact,
)
from app.services.whatsapp_webhook_parser import (
    parse_history_messages,
    parse_message_echoes,
    parse_state_sync_contacts,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Coexistence Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_whatsapp_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    phone_number_id: str = "PID_COEX",
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="WhatsApp Coexistence",
        public_key=f"wap_{uuid.uuid4().hex[:24]}",
        status="active",
        config_json={
            "provider": "meta_cloud_api",
            "onboarding_type": "embedded_signup_coexistence",
            "coexistence_enabled": True,
            "waba_id": "WABA1",
            "phone_number_id": phone_number_id,
            "display_phone_number": "+55 11 90000-0000",
            "auto_reply_enabled": True,
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _history_payload(
    phone_number_id: str = "PID_COEX",
    business_number: str = "551190000000",
    thread_wa_id: str = "5511888888888",
    messages: list[dict] | None = None,
    phase: int = 1,
    chunk_order: int = 0,
    progress: int = 50,
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA1",
                "changes": [
                    {
                        "field": "history",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": business_number,
                                "phone_number_id": phone_number_id,
                            },
                            "history": [
                                {
                                    "metadata": {
                                        "phase": phase,
                                        "chunk_order": chunk_order,
                                        "progress": progress,
                                    },
                                    "threads": [
                                        {
                                            "id": thread_wa_id,
                                            "messages": messages
                                            or [
                                                {
                                                    "from": thread_wa_id,
                                                    "to": business_number,
                                                    "id": "wamid.HIST1",
                                                    "timestamp": "1700000000",
                                                    "type": "text",
                                                    "text": {"body": "Oi, tudo bem?"},
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _state_sync_payload(
    phone_number_id: str = "PID_COEX",
    action: str = "add",
    contact_phone: str = "5511777777777",
    full_name: str | None = "Maria Contato",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA1",
                "changes": [
                    {
                        "field": "smb_app_state_sync",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": phone_number_id},
                            "state_sync": [
                                {
                                    "type": "contact",
                                    "contact": {
                                        "full_name": full_name,
                                        "first_name": "Maria",
                                        "phone_number": contact_phone,
                                    },
                                    "action": action,
                                    "metadata": {"timestamp": "1700000000"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _echo_payload(
    phone_number_id: str = "PID_COEX",
    from_number: str = "551190000000",
    to_number: str = "5511666666666",
    wamid: str = "wamid.ECHO1",
    text: str = "Já te respondo!",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA1",
                "changes": [
                    {
                        "field": "smb_message_echoes",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": phone_number_id},
                            "message_echoes": [
                                {
                                    "from": from_number,
                                    "to": to_number,
                                    "id": wamid,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


# ── Parser: history ──────────────────────────────────────────────────────────


class TestParseHistoryMessages:
    def test_extracts_message_with_metadata(self):
        payload = _history_payload()
        msgs = parse_history_messages(payload)
        assert len(msgs) == 1
        msg = msgs[0]
        assert msg.wamid == "wamid.HIST1"
        assert msg.phone_number_id == "PID_COEX"
        assert msg.thread_wa_id == "5511888888888"
        assert msg.text_body == "Oi, tudo bem?"
        assert msg.phase == 1
        assert msg.chunk_order == 0
        assert msg.progress == 50

    def test_direction_inbound_when_from_is_customer(self):
        msg = parse_history_messages(_history_payload())[0]
        assert msg.direction == "inbound"

    def test_direction_outbound_when_from_is_business_number(self):
        payload = _history_payload(
            messages=[
                {
                    "from": "551190000000",
                    "to": "5511888888888",
                    "id": "wamid.HIST2",
                    "timestamp": "1700000001",
                    "type": "text",
                    "text": {"body": "Claro, um segundo"},
                }
            ]
        )
        msg = parse_history_messages(payload)[0]
        assert msg.direction == "outbound"

    def test_non_text_message_gets_placeholder(self):
        payload = _history_payload(
            messages=[
                {
                    "from": "5511888888888",
                    "to": "551190000000",
                    "id": "wamid.HIST3",
                    "timestamp": "1700000002",
                    "type": "image",
                    "image": {"id": "media123"},
                }
            ]
        )
        msg = parse_history_messages(payload)[0]
        assert "image" in msg.text_body
        assert msg.message_type == "image"

    def test_message_missing_id_is_skipped(self):
        payload = _history_payload(
            messages=[{"from": "5511888888888", "to": "551190000000", "type": "text"}]
        )
        assert parse_history_messages(payload) == []

    def test_wrong_field_is_ignored(self):
        payload = _history_payload()
        payload["entry"][0]["changes"][0]["field"] = "messages"
        assert parse_history_messages(payload) == []

    def test_malformed_payload_returns_empty(self):
        assert parse_history_messages("not a dict") == []
        assert parse_history_messages({}) == []


# ── Parser: state sync ───────────────────────────────────────────────────────


class TestParseStateSyncContacts:
    def test_extracts_add_event(self):
        items = parse_state_sync_contacts(_state_sync_payload(action="add"))
        assert len(items) == 1
        assert items[0].action == "add"
        assert items[0].contact_phone == "5511777777777"
        assert items[0].full_name == "Maria Contato"

    def test_extracts_remove_event(self):
        items = parse_state_sync_contacts(_state_sync_payload(action="remove"))
        assert items[0].action == "remove"

    def test_unknown_action_is_skipped(self):
        payload = _state_sync_payload(action="update")
        assert parse_state_sync_contacts(payload) == []

    def test_missing_phone_is_skipped(self):
        payload = _state_sync_payload()
        del payload["entry"][0]["changes"][0]["value"]["state_sync"][0]["contact"]["phone_number"]
        assert parse_state_sync_contacts(payload) == []


# ── Parser: message echoes ───────────────────────────────────────────────────


class TestParseMessageEchoes:
    def test_extracts_echo(self):
        echoes = parse_message_echoes(_echo_payload())
        assert len(echoes) == 1
        assert echoes[0].wamid == "wamid.ECHO1"
        assert echoes[0].to_number == "5511666666666"
        assert echoes[0].text_body == "Já te respondo!"

    def test_missing_required_field_skipped(self):
        payload = _echo_payload()
        del payload["entry"][0]["changes"][0]["value"]["message_echoes"][0]["id"]
        assert parse_message_echoes(payload) == []


# ── Service: history import ──────────────────────────────────────────────────


class TestProcessHistoryMessage:
    def test_creates_contact_conversation_and_message(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [msg] = parse_history_messages(_history_payload())
        process_history_message(db, msg)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == "whatsapp:5511888888888")
        )
        assert contact is not None

        conv = db.scalar(select(Conversation).where(Conversation.contact_id == contact.id))
        assert conv is not None

        stored = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "wamid.HIST1"
            )
        )
        assert stored is not None
        assert stored.direction == "inbound"
        assert stored.sender_type == "customer"
        assert stored.content == "Oi, tudo bem?"
        assert stored.metadata_json["imported_from"] == "whatsapp_business_app_history"

    def test_preserves_original_whatsapp_timestamp(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [msg] = parse_history_messages(_history_payload())
        process_history_message(db, msg)

        stored = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "wamid.HIST1"
            )
        )
        assert stored.created_at.timestamp() == 1700000000

    def test_does_not_consume_usage_counter(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [msg] = parse_history_messages(_history_payload())
        process_history_message(db, msg)

        counters = list(
            db.scalars(
                select(UsageCounter).where(UsageCounter.workspace_id == workspace_a.id)
            ).all()
        )
        assert counters == []

    def test_duplicate_wamid_is_idempotent(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [msg] = parse_history_messages(_history_payload())
        process_history_message(db, msg)
        process_history_message(db, msg)

        all_msgs = list(
            db.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.external_message_id == "wamid.HIST1"
                )
            ).all()
        )
        assert len(all_msgs) == 1

    def test_unknown_channel_is_noop(self, db: Session, workspace_a: Workspace):
        [msg] = parse_history_messages(_history_payload(phone_number_id="NOPE"))
        process_history_message(db, msg)  # must not raise
        assert db.scalar(select(Contact)) is None


# ── Service: state sync ──────────────────────────────────────────────────────


class TestProcessStateSyncContact:
    def test_add_creates_contact(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [item] = parse_state_sync_contacts(_state_sync_payload(action="add"))
        process_state_sync_contact(db, item)

        contact = db.scalar(
            select(Contact).where(Contact.external_id == "whatsapp:5511777777777")
        )
        assert contact is not None
        assert contact.name == "Maria Contato"

    def test_remove_does_not_delete_anything(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [add_item] = parse_state_sync_contacts(_state_sync_payload(action="add"))
        process_state_sync_contact(db, add_item)

        [remove_item] = parse_state_sync_contacts(_state_sync_payload(action="remove"))
        process_state_sync_contact(db, remove_item)  # must not raise or delete

        contact = db.scalar(
            select(Contact).where(Contact.external_id == "whatsapp:5511777777777")
        )
        assert contact is not None

    def test_unknown_channel_is_noop(self, db: Session, workspace_a: Workspace):
        [item] = parse_state_sync_contacts(_state_sync_payload(phone_number_id="NOPE"))
        process_state_sync_contact(db, item)  # must not raise
        assert db.scalar(select(Contact)) is None


# ── Service: message echoes ──────────────────────────────────────────────────


class TestProcessMessageEcho:
    def test_creates_outbound_human_message(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [echo] = parse_message_echoes(_echo_payload())
        process_message_echo(db, echo)

        stored = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "wamid.ECHO1"
            )
        )
        assert stored is not None
        assert stored.direction == "outbound"
        assert stored.sender_type == "human"
        assert stored.sender_user_id is None
        assert stored.content == "Já te respondo!"

    def test_pauses_ai_on_conversation(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [echo] = parse_message_echoes(_echo_payload())
        process_message_echo(db, echo)

        conv = db.scalar(select(Conversation).where(Conversation.workspace_id == workspace_a.id))
        assert conv.ai_enabled is False
        assert conv.handoff_reason == "Dono respondeu pelo WhatsApp Business App"

    def test_duplicate_wamid_is_idempotent(self, db: Session, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id)

        [echo] = parse_message_echoes(_echo_payload())
        process_message_echo(db, echo)
        process_message_echo(db, echo)

        all_msgs = list(
            db.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.external_message_id == "wamid.ECHO1"
                )
            ).all()
        )
        assert len(all_msgs) == 1

    def test_unknown_channel_is_noop(self, db: Session, workspace_a: Workspace):
        [echo] = parse_message_echoes(_echo_payload(phone_number_id="NOPE"))
        process_message_echo(db, echo)  # must not raise
        assert db.scalar(select(ConversationMessage)) is None
