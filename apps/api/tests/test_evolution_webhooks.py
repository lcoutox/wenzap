"""Tests for the Evolution API webhook endpoint (Slice 3 — inbound).

POST /webhooks/whatsapp/evolution/{instance_name}

Covers:
  - valid payload + correct apikey creates ConversationMessage + Contact
  - unknown instance returns 200, no processing
  - wrong apikey returns 200, no message created
  - fromMe=true (echo of our own send) returns 200, no message created
  - malformed payload returns 200, no crash
  - duplicate wamid does not create a second message (idempotency, reused from
    whatsapp_inbound_service — same guarantee as the Meta path)
"""

import uuid

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
from app.models.user import User
from app.models.workspace import Workspace

TEST_API_KEY_ENV_VAR = "EVOLUTION_WEBHOOK_TEST_KEY"
TEST_API_KEY_VALUE = "test-evolution-key-xyz"


@pytest.fixture()
def public_webhook_client(db: Session):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _evolution_api_key_env(monkeypatch):
    monkeypatch.setenv(TEST_API_KEY_ENV_VAR, TEST_API_KEY_VALUE)


def _make_workspace(db: Session) -> Workspace:
    user = User(email=f"evo-owner-{uuid.uuid4().hex[:8]}@test.com", name="Evo Owner")
    db.add(user)
    db.flush()
    ws = Workspace(
        name="Evo WS",
        slug=f"evo-ws-{uuid.uuid4().hex[:8]}",
        status="active",
        owner_user_id=user.id,
    )
    db.add(ws)
    db.flush()
    return ws


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Evo Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_evolution_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    instance_name: str = "wenzap-test",
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="Evolution Test",
        public_key=f"wap_{uuid.uuid4().hex[:24]}",
        status="active",
        config_json={
            "provider": "evolution_api",
            "onboarding_type": "qr_code",
            "base_url": "https://nexevolution.up.railway.app",
            "instance_name": instance_name,
            "display_phone_number": None,
            "api_key_ref": f"env:{TEST_API_KEY_ENV_VAR}",
            "status": "active",
            "connected_at": None,
            "last_webhook_at": None,
            "auto_reply_enabled": False,
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _payload(
    instance: str = "wenzap-test",
    from_wa_id: str = "553784111441",
    wamid: str = "3EB0031990398D2F8A5B32",
    text: str = "Boa noite",
    from_me: bool = False,
    apikey: str = TEST_API_KEY_VALUE,
) -> dict:
    return {
        "event": "messages.upsert",
        "instance": instance,
        "data": {
            "key": {
                "remoteJid": f"{from_wa_id}@s.whatsapp.net",
                "fromMe": from_me,
                "id": wamid,
            },
            "pushName": "Lucas Couto",
            "message": {"conversation": text},
            "messageType": "conversation",
            "messageTimestamp": 1783982199,
        },
        "apikey": apikey,
    }


# ── success ───────────────────────────────────────────────────────────────────


class TestEvolutionWebhookSuccess:
    def test_valid_payload_returns_200(
        self, db: Session, public_webhook_client: TestClient
    ):
        ws = _make_workspace(db)
        agent = _make_agent(db, ws.id)
        _make_evolution_channel(db, ws.id, agent.id, instance_name="wenzap-test")
        db.commit()

        resp = public_webhook_client.post(
            "/webhooks/whatsapp/evolution/wenzap-test", json=_payload()
        )
        assert resp.status_code == 200

    def test_valid_payload_creates_message_and_contact(
        self, db: Session, public_webhook_client: TestClient
    ):
        ws = _make_workspace(db)
        agent = _make_agent(db, ws.id)
        _make_evolution_channel(db, ws.id, agent.id, instance_name="wenzap-test")
        db.commit()

        public_webhook_client.post(
            "/webhooks/whatsapp/evolution/wenzap-test",
            json=_payload(wamid="MSG_UNIQUE_1", text="Oi, tudo bem?"),
        )

        message = db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "MSG_UNIQUE_1"
            )
        )
        assert message is not None
        assert message.content == "Oi, tudo bem?"
        assert message.direction == "inbound"
        assert message.sender_type == "customer"

        contact = db.scalar(
            select(Contact).where(Contact.workspace_id == ws.id)
        )
        assert contact is not None
        assert contact.external_id == "whatsapp:553784111441"

    def test_duplicate_wamid_does_not_duplicate_message(
        self, db: Session, public_webhook_client: TestClient
    ):
        ws = _make_workspace(db)
        agent = _make_agent(db, ws.id)
        _make_evolution_channel(db, ws.id, agent.id, instance_name="wenzap-test")
        db.commit()

        payload = _payload(wamid="MSG_DUP", text="Repetida")
        public_webhook_client.post("/webhooks/whatsapp/evolution/wenzap-test", json=payload)
        public_webhook_client.post("/webhooks/whatsapp/evolution/wenzap-test", json=payload)

        count = len(
            db.scalars(
                select(ConversationMessage).where(
                    ConversationMessage.external_message_id == "MSG_DUP"
                )
            ).all()
        )
        assert count == 1


# ── rejection paths — all return 200, but do NOT process ────────────────────


class TestEvolutionWebhookRejection:
    def test_unknown_instance_returns_200_no_message(
        self, db: Session, public_webhook_client: TestClient
    ):
        resp = public_webhook_client.post(
            "/webhooks/whatsapp/evolution/does-not-exist",
            json=_payload(instance="does-not-exist", wamid="MSG_UNKNOWN"),
        )
        assert resp.status_code == 200
        assert db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "MSG_UNKNOWN"
            )
        ) is None

    def test_wrong_apikey_returns_200_no_message(
        self, db: Session, public_webhook_client: TestClient
    ):
        ws = _make_workspace(db)
        agent = _make_agent(db, ws.id)
        _make_evolution_channel(db, ws.id, agent.id, instance_name="wenzap-test")
        db.commit()

        resp = public_webhook_client.post(
            "/webhooks/whatsapp/evolution/wenzap-test",
            json=_payload(wamid="MSG_BADKEY", apikey="wrong-key"),
        )
        assert resp.status_code == 200
        assert db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "MSG_BADKEY"
            )
        ) is None

    def test_from_me_echo_returns_200_no_message(
        self, db: Session, public_webhook_client: TestClient
    ):
        ws = _make_workspace(db)
        agent = _make_agent(db, ws.id)
        _make_evolution_channel(db, ws.id, agent.id, instance_name="wenzap-test")
        db.commit()

        resp = public_webhook_client.post(
            "/webhooks/whatsapp/evolution/wenzap-test",
            json=_payload(wamid="MSG_ECHO", from_me=True),
        )
        assert resp.status_code == 200
        assert db.scalar(
            select(ConversationMessage).where(
                ConversationMessage.external_message_id == "MSG_ECHO"
            )
        ) is None

    def test_malformed_payload_returns_200(
        self, db: Session, public_webhook_client: TestClient
    ):
        ws = _make_workspace(db)
        agent = _make_agent(db, ws.id)
        _make_evolution_channel(db, ws.id, agent.id, instance_name="wenzap-test")
        db.commit()

        resp = public_webhook_client.post(
            "/webhooks/whatsapp/evolution/wenzap-test", json={"garbage": True}
        )
        assert resp.status_code == 200

    def test_empty_body_returns_200(
        self, db: Session, public_webhook_client: TestClient
    ):
        resp = public_webhook_client.post(
            "/webhooks/whatsapp/evolution/wenzap-test", content=b""
        )
        assert resp.status_code == 200
