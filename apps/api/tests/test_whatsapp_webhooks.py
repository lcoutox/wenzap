"""
Tests for WhatsApp webhook endpoints — Phase 6.0 + 6.2-A.

Covers:
  GET /webhooks/whatsapp/meta (hub challenge verification)
  - valid token returns 200 with challenge body
  - wrong token returns 403
  - wrong mode returns 403
  - missing params return 403
  - empty settings token returns 403

  POST /webhooks/whatsapp/meta (inbound receiver — Phase 6.2-A)
  - valid text payload returns 200
  - valid text payload creates ConversationMessage in DB
  - valid text payload creates Contact in DB
  - status update payload returns 200 without creating message
  - channel not found returns 200 (no crash)
  - malformed payload returns 200 (no crash)
  - empty payload returns 200 (no crash)
  - second POST with same wamid returns 200 but does not duplicate message
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models.agent import Agent
from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation_message import ConversationMessage
from app.models.workspace import Workspace

VERIFY_URL = "/webhooks/whatsapp/meta"
VALID_TOKEN = "test_verify_token_abc"


# ── Client fixtures ───────────────────────────────────────────────────────────


@pytest.fixture()
def client():
    """Unauthenticated client — webhook endpoints are public."""
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture()
def public_webhook_client(db: Session):
    """Client with DB override for tests that verify DB state."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def patch_verify_token():
    """Inject a known verify token into settings for all tests."""
    with patch("app.routers.whatsapp_webhooks.settings") as mock_settings:
        mock_settings.whatsapp_webhook_verify_token = VALID_TOKEN
        yield mock_settings


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="WA Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_whatsapp_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    phone_number_id: str,
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="WA Test",
        public_key=f"wap_{uuid.uuid4().hex[:24]}",
        status="active",
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
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _text_payload(
    phone_number_id: str = "PID_ENDPOINT_TEST",
    wa_id: str = "5537900000001",
    wamid: str = "wamid.ENDPOINT001",
    text_body: str = "Olá",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15556620073",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "Test User"}, "wa_id": wa_id}
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": wamid,
                                    "timestamp": "1710000000",
                                    "text": {"body": text_body},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _status_payload(wamid: str = "wamid.STATUS001") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": wamid,
                                    "status": "delivered",
                                    "timestamp": "1710000001",
                                    "recipient_id": "5537900000001",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


# ── GET verification ──────────────────────────────────────────────────────────


class TestWhatsAppVerifyGet:
    def test_valid_token_returns_200(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "challenge123",
        })
        assert resp.status_code == 200

    def test_valid_token_returns_challenge_body(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "my_challenge_value",
        })
        assert resp.text == "my_challenge_value"

    def test_valid_token_returns_plain_text(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "abc",
        })
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_wrong_token_returns_403(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "abc",
        })
        assert resp.status_code == 403

    def test_wrong_mode_returns_403(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "abc",
        })
        assert resp.status_code == 403

    def test_missing_mode_returns_403(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.verify_token": VALID_TOKEN,
            "hub.challenge": "abc",
        })
        assert resp.status_code == 403

    def test_missing_token_returns_403(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "subscribe",
            "hub.challenge": "abc",
        })
        assert resp.status_code == 403

    def test_empty_token_in_settings_returns_403(self, client: TestClient):
        with patch("app.routers.whatsapp_webhooks.settings") as mock:
            mock.whatsapp_webhook_verify_token = ""
            resp = client.get(VERIFY_URL, params={
                "hub.mode": "subscribe",
                "hub.verify_token": "",
                "hub.challenge": "abc",
            })
        assert resp.status_code == 403

    def test_missing_challenge_returns_200_with_empty_body(self, client: TestClient):
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
        })
        assert resp.status_code == 200
        assert resp.text == ""


# ── POST receiver ─────────────────────────────────────────────────────────────


class TestWhatsAppReceivePost:
    def test_valid_text_payload_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json=_text_payload())
        assert resp.status_code == 200

    def test_valid_text_payload_returns_ok_body(self, client: TestClient):
        resp = client.post(VERIFY_URL, json=_text_payload())
        assert resp.json() == {"status": "ok"}

    def test_status_update_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json=_status_payload())
        assert resp.status_code == 200

    def test_empty_payload_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json={})
        assert resp.status_code == 200

    def test_unexpected_payload_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json={"unexpected": "field"})
        assert resp.status_code == 200

    def test_no_auth_required(self, client: TestClient):
        resp = client.post(VERIFY_URL, json={"object": "test"})
        assert resp.status_code == 200

    def test_channel_not_found_returns_200(self, client: TestClient):
        """Unknown phone_number_id must not crash the endpoint."""
        resp = client.post(VERIFY_URL, json=_text_payload(phone_number_id="PID_UNKNOWN_XYZ"))
        assert resp.status_code == 200

    def test_valid_text_creates_message_in_db(
        self, db: Session, workspace_a: Workspace, public_webhook_client: TestClient
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="PID_DB_TEST")

        public_webhook_client.post(
            VERIFY_URL,
            json=_text_payload(phone_number_id="PID_DB_TEST", wamid="wamid.DB_CREATE"),
        )

        msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "wamid.DB_CREATE"
            )
        )
        assert msg is not None
        assert msg.direction == "inbound"
        assert msg.sender_type == "customer"

    def test_valid_text_creates_contact_in_db(
        self, db: Session, workspace_a: Workspace, public_webhook_client: TestClient
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="PID_CONTACT_TEST")

        public_webhook_client.post(
            VERIFY_URL,
            json=_text_payload(
                phone_number_id="PID_CONTACT_TEST",
                wa_id="5537800000001",
                wamid="wamid.CONTACT_CREATE",
            ),
        )

        contact = db.scalar(
            select(Contact).where(
                Contact.workspace_id == workspace_a.id,
                Contact.external_id == "whatsapp:5537800000001",
            )
        )
        assert contact is not None

    def test_status_update_does_not_create_message(
        self, db: Session, workspace_a: Workspace, public_webhook_client: TestClient
    ):
        public_webhook_client.post(VERIFY_URL, json=_status_payload(wamid="wamid.STATUS_NO_MSG"))

        msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.workspace_id == workspace_a.id
            )
        )
        assert msg is None

    def test_duplicate_wamid_does_not_create_second_message(
        self, db: Session, workspace_a: Workspace, public_webhook_client: TestClient
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="PID_IDEM_TEST")

        payload = _text_payload(phone_number_id="PID_IDEM_TEST", wamid="wamid.IDEM001")
        public_webhook_client.post(VERIFY_URL, json=payload)
        public_webhook_client.post(VERIFY_URL, json=payload)

        messages = list(
            db.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.external_message_id == "wamid.IDEM001"
                )
            ).all()
        )
        assert len(messages) == 1


def _status_payload_full(
    wamid: str = "wamid.ST001",
    status: str = "delivered",
    timestamp: str = "1710000005",
    errors: list | None = None,
) -> dict:
    status_obj: dict = {
        "id": wamid,
        "status": status,
        "timestamp": timestamp,
        "recipient_id": "5537900000001",
        "conversation": {
            "id": "wamid-conv-001",
            "origin": {"type": "service"},
        },
        "pricing": {
            "billable": True,
            "pricing_model": "CBP",
            "category": "service",
        },
    }
    if errors:
        status_obj["errors"] = errors
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "PID_STATUS_EP"},
                            "statuses": [status_obj],
                        },
                    }
                ]
            }
        ],
    }


def _seed_outbound_msg(
    db: Session,
    workspace: Workspace,
    wamid: str = "wamid.ST001",
) -> ConversationMessage:
    from app.models.agent import Agent
    from app.models.contact import Contact
    from app.models.conversation import Conversation

    agent = Agent(workspace_id=workspace.id, name="Agent-st")
    db.add(agent)
    db.flush()
    contact = Contact(workspace_id=workspace.id, name="C", external_id="whatsapp:55379")
    db.add(contact)
    db.flush()
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
    msg = ConversationMessage(
        workspace_id=workspace.id,
        conversation_id=conv.id,
        direction="outbound",
        sender_type="human",
        content="Oi",
        external_message_id=wamid,
        metadata_json={"delivery": {"status": "sent", "sent_at": "2026-06-26T12:00:00+00:00"}},
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


class TestStatusUpdateEndpoint:
    def test_status_delivered_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json=_status_payload_full())
        assert resp.status_code == 200

    def test_status_delivered_updates_existing_message(
        self, db: Session, workspace_a: Workspace, public_webhook_client: TestClient
    ):
        msg = _seed_outbound_msg(db, workspace_a, wamid="wamid.EP_DELIVERED")
        public_webhook_client.post(
            VERIFY_URL, json=_status_payload_full(wamid="wamid.EP_DELIVERED", status="delivered")
        )
        db.refresh(msg)
        assert msg.metadata_json["delivery"]["status"] == "delivered"

    def test_status_failed_saves_error_code(
        self, db: Session, workspace_a: Workspace, public_webhook_client: TestClient
    ):
        msg = _seed_outbound_msg(db, workspace_a, wamid="wamid.EP_FAILED")
        errors = [{"code": 130497, "title": "Country restricted", "message": "Restricted."}]
        public_webhook_client.post(
            VERIFY_URL,
            json=_status_payload_full(wamid="wamid.EP_FAILED", status="failed", errors=errors),
        )
        db.refresh(msg)
        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "failed"
        assert delivery["error_code"] == "130497"

    def test_status_unknown_returns_200(self, client: TestClient):
        payload = _status_payload_full(status="processing")
        resp = client.post(VERIFY_URL, json=payload)
        assert resp.status_code == 200

    def test_status_for_unknown_wamid_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json=_status_payload_full(wamid="wamid.NOT_IN_DB"))
        assert resp.status_code == 200

    def test_mixed_payload_processes_both_inbound_and_status(
        self, db: Session, workspace_a: Workspace, public_webhook_client: TestClient
    ):
        """A payload with both messages[] and statuses[] must process both."""
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="PID_MIXED")
        outbound = _seed_outbound_msg(db, workspace_a, wamid="wamid.MIXED_STATUS")

        mixed_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID_MIXED"},
                                "contacts": [
                                    {"profile": {"name": "Usr"}, "wa_id": "5537900000099"}
                                ],
                                "messages": [
                                    {
                                        "from": "5537900000099",
                                        "id": "wamid.MIXED_INBOUND",
                                        "timestamp": "1710000099",
                                        "type": "text",
                                        "text": {"body": "Oi"},
                                    }
                                ],
                                "statuses": [
                                    {
                                        "id": "wamid.MIXED_STATUS",
                                        "status": "delivered",
                                        "timestamp": "1710000100",
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        public_webhook_client.post(VERIFY_URL, json=mixed_payload)

        # Inbound message created
        inbound_msg = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "wamid.MIXED_INBOUND"
            )
        )
        assert inbound_msg is not None

        # Outbound status updated
        db.refresh(outbound)
        assert outbound.metadata_json["delivery"]["status"] == "delivered"
