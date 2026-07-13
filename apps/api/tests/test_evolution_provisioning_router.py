"""Integration tests for Evolution provisioning endpoints — Slice 4.

POST /channels/whatsapp/evolution/connect
GET  /channels/whatsapp/evolution/{channel_id}/status
POST /channels/whatsapp/evolution/{channel_id}/disconnect
"""

import uuid
from unittest.mock import MagicMock, patch

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.workspace import Workspace

_SETTINGS_PATCH = "app.services.evolution_provisioning_service.settings"
_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Evo Router Agent", status="active")
    db.add(agent)
    db.flush()
    db.commit()
    db.refresh(agent)
    return agent


def _mock_settings(**overrides):
    defaults = dict(
        evolution_api_base_url="https://nexevolution.up.railway.app",
        evolution_master_api_key="master-key-xyz",
        api_public_base_url="https://api.wenzap.com.br",
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _create_instance_response(instance_name: str) -> httpx.Response:
    body = {
        "instance": {"instanceName": instance_name, "status": "connecting"},
        "hash": "TOKEN_ROUTER_TEST",
        "qrcode": {"pairingCode": None, "code": "raw", "base64": "data:image/png;base64,ZZZZ"},
    }
    return httpx.Response(201, json=body, request=httpx.Request("POST", "https://x/instance/create"))


def _encrypted_env():
    return (
        patch(_SETTINGS_PATCH, _mock_settings()),
        patch("app.services.crypto_service.settings.app_encryption_key", _TEST_ENCRYPTION_KEY),
    )


# ── POST /connect ────────────────────────────────────────────────────────────


class TestConnect:
    def test_success_returns_qrcode(
        self, db: Session, workspace_a: Workspace, client_a: TestClient,
        growth_subscription_a,
    ):
        agent = _make_agent(db, workspace_a.id)

        p1, p2 = _encrypted_env()
        with p1, p2, patch("httpx.post") as mock_post:
            mock_post.side_effect = [
                _create_instance_response("wenzap-router1"),
                httpx.Response(200, json={}, request=httpx.Request("POST", "https://x/webhook/set")),
            ]
            resp = client_a.post(
                "/channels/whatsapp/evolution/connect", json={"agent_id": str(agent.id)}
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["qrcode_base64"] == "data:image/png;base64,ZZZZ"
        assert body["channel"]["config"]["provider"] == "evolution_api"

    def test_unknown_agent_returns_404(
        self, db: Session, workspace_a: Workspace, client_a: TestClient,
        growth_subscription_a,
    ):
        p1, p2 = _encrypted_env()
        with p1, p2:
            resp = client_a.post(
                "/channels/whatsapp/evolution/connect", json={"agent_id": str(uuid.uuid4())}
            )
        assert resp.status_code == 404

    def test_evolution_create_failure_returns_502(
        self, db: Session, workspace_a: Workspace, client_a: TestClient,
        growth_subscription_a,
    ):
        agent = _make_agent(db, workspace_a.id)
        p1, p2 = _encrypted_env()
        with p1, p2, patch("httpx.post", side_effect=httpx.ConnectError("down")):
            resp = client_a.post(
                "/channels/whatsapp/evolution/connect", json={"agent_id": str(agent.id)}
            )
        assert resp.status_code == 502


# ── GET /{channel_id}/status ─────────────────────────────────────────────────


class TestStatus:
    def test_polls_and_returns_state(
        self, db: Session, workspace_a: Workspace, client_a: TestClient,
        growth_subscription_a,
    ):
        agent = _make_agent(db, workspace_a.id)
        p1, p2 = _encrypted_env()
        with p1, p2:
            with patch("httpx.post") as mock_post:
                mock_post.side_effect = [
                    _create_instance_response("wenzap-router2"),
                    httpx.Response(
                        200, json={}, request=httpx.Request("POST", "https://x/webhook/set")
                    ),
                ]
                connect_resp = client_a.post(
                    "/channels/whatsapp/evolution/connect", json={"agent_id": str(agent.id)}
                )
            channel_id = connect_resp.json()["channel"]["id"]

            instance_data = {"instanceName": "wenzap-router2", "state": "open"}
            get_resp = httpx.Response(
                200, json={"instance": instance_data}, request=httpx.Request("GET", "https://x")
            )
            with patch("httpx.get", return_value=get_resp):
                resp = client_a.get(f"/channels/whatsapp/evolution/{channel_id}/status")

        assert resp.status_code == 200
        assert resp.json()["state"] == "open"

    def test_unknown_channel_returns_404(
        self, workspace_a: Workspace, client_a: TestClient,
    ):
        resp = client_a.get(f"/channels/whatsapp/evolution/{uuid.uuid4()}/status")
        assert resp.status_code == 404


# ── POST /{channel_id}/disconnect ────────────────────────────────────────────


class TestDisconnect:
    def test_disconnect_archives_channel(
        self, db: Session, workspace_a: Workspace, client_a: TestClient,
        growth_subscription_a,
    ):
        agent = _make_agent(db, workspace_a.id)
        p1, p2 = _encrypted_env()
        with p1, p2, patch("httpx.post") as mock_post:
            mock_post.side_effect = [
                _create_instance_response("wenzap-router3"),
                httpx.Response(200, json={}, request=httpx.Request("POST", "https://x/webhook/set")),
            ]
            connect_resp = client_a.post(
                "/channels/whatsapp/evolution/connect", json={"agent_id": str(agent.id)}
            )
        channel_id = connect_resp.json()["channel"]["id"]

        delete_resp = httpx.Response(
            200, json={"status": "SUCCESS"}, request=httpx.Request("DELETE", "https://x")
        )
        with patch(_SETTINGS_PATCH, _mock_settings()), \
             patch("httpx.delete", return_value=delete_resp):
            resp = client_a.post(f"/channels/whatsapp/evolution/{channel_id}/disconnect")

        assert resp.status_code == 204

    def test_unknown_channel_returns_404(
        self, workspace_a: Workspace, client_a: TestClient,
    ):
        resp = client_a.post(f"/channels/whatsapp/evolution/{uuid.uuid4()}/disconnect")
        assert resp.status_code == 404
