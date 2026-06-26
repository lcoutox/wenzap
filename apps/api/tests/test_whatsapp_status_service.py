"""
Integration tests for whatsapp_status_service — Phase 6.4-A.

Uses a real DB session (via the `db` fixture from conftest.py).
No HTTP calls — status updates arrive as already-parsed WhatsAppStatusUpdate objects.

Covers:
  should_update_status (pure function)
  - known statuses advance in order
  - regression is rejected
  - failed always overwrites
  - unknown status never overwrites

  process_status_update
  - delivered updates delivery.status and delivered_at
  - read updates delivery.status and read_at
  - failed saves error_code, error_title, error_message, failed_at
  - preserves existing sent_at when delivered arrives
  - preserves existing sent_at and delivered_at when read arrives
  - wamid not found returns None without raising
  - inbound message with same wamid is not updated
  - read → delivered does not regress status
  - delivered → sent does not regress status
  - failed overwrites read (terminal error)
  - unknown status saves last_status_raw but does not alter delivery.status
  - pricing saved correctly in delivery.pricing
  - meta_conversation_id and conversation_origin_type saved
  - sequence sent → delivered → read accumulates all timestamps
  - last_status_at and last_status_raw always updated
  - no metadata_json on message defaults gracefully
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.workspace import Workspace
from app.services.whatsapp_status_service import process_status_update, should_update_status
from app.services.whatsapp_webhook_parser import WhatsAppStatusUpdate

# ── Helpers ────────────────────────────────────────────────────────────────────


def _seed_agent(db: Session, workspace: Workspace) -> Agent:
    a = Agent(workspace_id=workspace.id, name=f"Agent-{uuid.uuid4().hex[:6]}")
    db.add(a)
    db.flush()
    return a


def _seed_contact(db: Session, workspace: Workspace) -> Contact:
    c = Contact(
        workspace_id=workspace.id,
        name="WA Contact",
        phone="+5537888000001",
        external_id="whatsapp:5537888000001",
    )
    db.add(c)
    db.flush()
    return c


def _seed_conversation(
    db: Session, workspace: Workspace, contact: Contact, agent: Agent
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        agent_id=agent.id,
        channel_type="whatsapp",
        status="open",
        ai_enabled=False,
    )
    db.add(conv)
    db.flush()
    return conv


def _seed_outbound_message(
    db: Session,
    workspace: Workspace,
    conversation: Conversation,
    wamid: str = "wamid.TEST001",
    direction: str = "outbound",
    metadata_json: dict | None = None,
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        direction=direction,
        sender_type="human",
        content="Olá",
        external_message_id=wamid,
        metadata_json=metadata_json or {
            "delivery": {
                "channel": "whatsapp",
                "status": "sent",
                "sent_at": "2026-06-26T12:00:00+00:00",
                "phone_number_id": "PID_TEST",
                "recipient": "5537888000001",
            }
        },
    )
    db.add(msg)
    db.flush()
    db.commit()
    db.refresh(msg)
    return msg


def _make_update(
    wamid: str = "wamid.TEST001",
    status: str = "delivered",
    timestamp: int | None = 1710000005,
    conversation_id: str | None = "wamid-conv-001",
    conversation_origin_type: str | None = "service",
    pricing_category: str | None = "service",
    pricing_model: str | None = "CBP",
    billable: bool | None = True,
    error_code: str | None = None,
    error_title: str | None = None,
    error_message: str | None = None,
) -> WhatsAppStatusUpdate:
    return WhatsAppStatusUpdate(
        phone_number_id="PID_TEST",
        wamid=wamid,
        status=status,
        timestamp=timestamp,
        recipient_id="5537888000001",
        conversation_id=conversation_id,
        conversation_origin_type=conversation_origin_type,
        pricing_category=pricing_category,
        pricing_model=pricing_model,
        billable=billable,
        error_code=error_code,
        error_title=error_title,
        error_message=error_message,
    )


# ── should_update_status (pure function) ──────────────────────────────────────


class TestShouldUpdateStatus:
    def test_none_to_sent(self):
        assert should_update_status(None, "sent") is True

    def test_sent_to_delivered(self):
        assert should_update_status("sent", "delivered") is True

    def test_delivered_to_read(self):
        assert should_update_status("delivered", "read") is True

    def test_read_to_delivered_is_rejected(self):
        assert should_update_status("read", "delivered") is False

    def test_delivered_to_sent_is_rejected(self):
        assert should_update_status("delivered", "sent") is False

    def test_read_to_sent_is_rejected(self):
        assert should_update_status("read", "sent") is False

    def test_failed_overwrites_sent(self):
        assert should_update_status("sent", "failed") is True

    def test_failed_overwrites_read(self):
        assert should_update_status("read", "failed") is True

    def test_failed_overwrites_none(self):
        assert should_update_status(None, "failed") is True

    def test_unknown_status_never_overwrites(self):
        assert should_update_status("delivered", "processing") is False
        assert should_update_status(None, "processing") is False

    def test_same_status_does_not_regress(self):
        assert should_update_status("delivered", "delivered") is False


# ── process_status_update (integration) ───────────────────────────────────────


class TestProcessStatusUpdate:
    @pytest.fixture(autouse=True)
    def _seed(self, db: Session, workspace_a: Workspace):
        self.ws = workspace_a
        self.agent = _seed_agent(db, self.ws)
        self.contact = _seed_contact(db, self.ws)
        self.conv = _seed_conversation(db, self.ws, self.contact, self.agent)
        self.db = db

    def test_delivered_updates_status(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        result = process_status_update(self.db, _make_update(wamid=msg.external_message_id))
        self.db.refresh(result)
        assert result.metadata_json["delivery"]["status"] == "delivered"

    def test_delivered_saves_delivered_at(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        process_status_update(
            self.db, _make_update(wamid=msg.external_message_id, timestamp=1710000005)
        )
        self.db.refresh(msg)
        assert "delivered_at" in msg.metadata_json["delivery"]

    def test_read_updates_status_and_read_at(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id, status="read", timestamp=1710000010
        ))
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "read"
        assert "read_at" in delivery

    def test_failed_saves_error_fields_and_failed_at(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id,
            status="failed",
            timestamp=1710000020,
            error_code="130497",
            error_title="Country restricted",
            error_message="Business account is restricted from messaging users in this country.",
        ))
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "failed"
        assert delivery["error_code"] == "130497"
        assert delivery["error_title"] == "Country restricted"
        assert "restricted" in delivery["error_message"]
        assert "failed_at" in delivery

    def test_delivered_preserves_existing_sent_at(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json={
                "delivery": {
                    "channel": "whatsapp",
                    "status": "sent",
                    "sent_at": "2026-06-26T12:00:00+00:00",
                }
            },
        )
        process_status_update(self.db, _make_update(wamid=msg.external_message_id))
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["sent_at"] == "2026-06-26T12:00:00+00:00"
        assert delivery["status"] == "delivered"

    def test_read_preserves_sent_at_and_delivered_at(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json={
                "delivery": {
                    "status": "delivered",
                    "sent_at": "2026-06-26T12:00:00+00:00",
                    "delivered_at": "2026-06-26T12:00:05+00:00",
                }
            },
        )
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id, status="read", timestamp=1710000010
        ))
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["sent_at"] == "2026-06-26T12:00:00+00:00"
        assert delivery["delivered_at"] == "2026-06-26T12:00:05+00:00"
        assert "read_at" in delivery

    def test_wamid_not_found_returns_none_without_raising(self):
        result = process_status_update(
            self.db, _make_update(wamid="wamid.DOES_NOT_EXIST")
        )
        assert result is None

    def test_inbound_message_with_same_wamid_is_not_updated(self):
        inbound = _seed_outbound_message(
            self.db, self.ws, self.conv,
            wamid="wamid.INBOUND_ONLY",
            direction="inbound",
            metadata_json={"delivery": {"status": "received"}},
        )
        result = process_status_update(
            self.db, _make_update(wamid="wamid.INBOUND_ONLY", status="delivered")
        )
        assert result is None
        self.db.refresh(inbound)
        assert inbound.metadata_json["delivery"]["status"] == "received"

    def test_read_to_delivered_does_not_regress(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json={"delivery": {"status": "read"}},
        )
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id, status="delivered"
        ))
        self.db.refresh(msg)
        assert msg.metadata_json["delivery"]["status"] == "read"

    def test_delivered_to_sent_does_not_regress(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json={"delivery": {"status": "delivered"}},
        )
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id, status="sent"
        ))
        self.db.refresh(msg)
        assert msg.metadata_json["delivery"]["status"] == "delivered"

    def test_failed_overwrites_read(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json={"delivery": {"status": "read"}},
        )
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id,
            status="failed",
            error_code="131026",
            error_title="Message undeliverable",
            error_message="The message could not be delivered.",
        ))
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "failed"
        assert delivery["error_code"] == "131026"

    def test_unknown_status_saves_last_status_raw_but_does_not_alter_status(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json={"delivery": {"status": "delivered"}},
        )
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id, status="processing"
        ))
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "delivered"
        assert delivery["last_status_raw"] == "processing"

    def test_pricing_saved_correctly(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id,
            pricing_category="service",
            pricing_model="CBP",
            billable=True,
        ))
        self.db.refresh(msg)
        pricing = msg.metadata_json["delivery"]["pricing"]
        assert pricing["category"] == "service"
        assert pricing["pricing_model"] == "CBP"
        assert pricing["billable"] is True

    def test_meta_conversation_id_and_origin_type_saved(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        process_status_update(self.db, _make_update(
            wamid=msg.external_message_id,
            conversation_id="wamid-conv-XYZ",
            conversation_origin_type="marketing",
        ))
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["meta_conversation_id"] == "wamid-conv-XYZ"
        assert delivery["conversation_origin_type"] == "marketing"

    def test_sequence_sent_delivered_read_accumulates_timestamps(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json={
                "delivery": {
                    "status": "sent",
                    "sent_at": "2026-06-26T12:00:00+00:00",
                }
            },
        )
        wamid = msg.external_message_id

        process_status_update(
            self.db, _make_update(wamid=wamid, status="delivered", timestamp=1710000005)
        )
        self.db.refresh(msg)
        assert msg.metadata_json["delivery"]["status"] == "delivered"
        assert "delivered_at" in msg.metadata_json["delivery"]

        process_status_update(
            self.db, _make_update(wamid=wamid, status="read", timestamp=1710000010)
        )
        self.db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "read"
        assert delivery["sent_at"] == "2026-06-26T12:00:00+00:00"
        assert "delivered_at" in delivery
        assert "read_at" in delivery

    def test_last_status_at_always_updated(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        process_status_update(self.db, _make_update(wamid=msg.external_message_id))
        self.db.refresh(msg)
        assert "last_status_at" in msg.metadata_json["delivery"]

    def test_last_status_raw_always_updated(self):
        msg = _seed_outbound_message(self.db, self.ws, self.conv)
        process_status_update(self.db, _make_update(wamid=msg.external_message_id, status="read"))
        self.db.refresh(msg)
        assert msg.metadata_json["delivery"]["last_status_raw"] == "read"

    def test_message_with_no_metadata_json_defaults_gracefully(self):
        msg = _seed_outbound_message(
            self.db, self.ws, self.conv,
            metadata_json=None,
        )
        result = process_status_update(self.db, _make_update(wamid=msg.external_message_id))
        assert result is not None
        self.db.refresh(result)
        assert result.metadata_json["delivery"]["status"] == "delivered"
