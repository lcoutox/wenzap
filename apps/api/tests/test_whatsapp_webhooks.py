"""
Tests for Phase 6.0 — WhatsApp Webhook Foundation.

Covers:
- GET /webhooks/whatsapp/meta (hub challenge verification)
- POST /webhooks/whatsapp/meta (inbound payload receiver)
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

VERIFY_URL = "/webhooks/whatsapp/meta"
VALID_TOKEN = "test_verify_token_abc"


@pytest.fixture()
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def patch_verify_token():
    """Inject a known verify token into settings for all tests."""
    with patch("app.routers.whatsapp_webhooks.settings") as mock_settings:
        mock_settings.whatsapp_webhook_verify_token = VALID_TOKEN
        yield mock_settings


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
        """If WHATSAPP_WEBHOOK_VERIFY_TOKEN is not configured, always deny."""
        with patch("app.routers.whatsapp_webhooks.settings") as mock:
            mock.whatsapp_webhook_verify_token = ""
            resp = client.get(VERIFY_URL, params={
                "hub.mode": "subscribe",
                "hub.verify_token": "",
                "hub.challenge": "abc",
            })
        assert resp.status_code == 403

    def test_missing_challenge_returns_200_with_empty_body(self, client: TestClient):
        """Missing challenge → still verifies OK, returns empty body."""
        resp = client.get(VERIFY_URL, params={
            "hub.mode": "subscribe",
            "hub.verify_token": VALID_TOKEN,
        })
        assert resp.status_code == 200
        assert resp.text == ""


# ── POST receiver ─────────────────────────────────────────────────────────────

class TestWhatsAppReceivePost:
    def test_typical_payload_returns_200(self, client: TestClient):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [{"type": "text", "text": {"body": "Olá"}}],
                            },
                        }
                    ],
                }
            ],
        }
        resp = client.post(VERIFY_URL, json=payload)
        assert resp.status_code == 200

    def test_typical_payload_returns_ok_body(self, client: TestClient):
        resp = client.post(VERIFY_URL, json={"object": "whatsapp_business_account", "entry": []})
        assert resp.json() == {"status": "ok"}

    def test_empty_payload_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json={})
        assert resp.status_code == 200

    def test_unexpected_payload_returns_200(self, client: TestClient):
        resp = client.post(VERIFY_URL, json={"unexpected": "field", "foo": [1, 2, 3]})
        assert resp.status_code == 200

    def test_status_update_payload_returns_200(self, client: TestClient):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123",
                    "changes": [
                        {
                            "field": "statuses",
                            "value": {"statuses": [{"status": "delivered", "id": "msg_id"}]},
                        }
                    ],
                }
            ],
        }
        resp = client.post(VERIFY_URL, json=payload)
        assert resp.status_code == 200

    def test_no_auth_required(self, client: TestClient):
        """POST must not require Clerk authentication."""
        resp = client.post(VERIFY_URL, json={"object": "test"})
        assert resp.status_code == 200
