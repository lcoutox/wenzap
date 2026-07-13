"""Tests for evolution_provisioning_service.py — Slice 4 (QR provisioning).

Unit tests: no real HTTP calls to Evolution. httpx is monkeypatched throughout,
following the same pattern as test_whatsapp_embedded_signup.py.
"""

import uuid
from unittest.mock import MagicMock, patch

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.channel_credential import ChannelCredential
from app.models.user import User
from app.models.workspace import Workspace
from app.services import evolution_provisioning_service as svc

_SETTINGS_PATCH = "app.services.evolution_provisioning_service.settings"
_TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


def _make_workspace_and_agent(db: Session) -> tuple[Workspace, Agent]:
    user = User(email=f"evo-prov-{uuid.uuid4().hex[:8]}@test.com", name="Owner")
    db.add(user)
    db.flush()
    ws = Workspace(
        name="Evo Prov WS", slug=f"evo-prov-{uuid.uuid4().hex[:8]}",
        status="active", owner_user_id=user.id,
    )
    db.add(ws)
    db.flush()
    agent = Agent(workspace_id=ws.id, name="Evo Prov Agent", status="active")
    db.add(agent)
    db.flush()
    db.commit()
    return ws, agent


def _make_channel(
    db: Session, ws: Workspace, agent: Agent, instance_name: str = "wenzap-abc123"
) -> Channel:
    ch = Channel(
        workspace_id=ws.id, agent_id=agent.id, channel_type="whatsapp",
        name="Evo Test", public_key=f"wap_{uuid.uuid4().hex[:24]}", status="active",
        config_json={
            "provider": "evolution_api", "onboarding_type": "qr_code",
            "base_url": "https://nexevolution.up.railway.app",
            "instance_name": instance_name, "display_phone_number": None,
            "api_key_ref": None, "status": "testing",
            "connected_at": None, "last_webhook_at": None, "auto_reply_enabled": False,
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _create_instance_response(
    instance_name: str, token: str = "INSTANCE_TOKEN_1"
) -> httpx.Response:
    body = {
        "instance": {"instanceName": instance_name, "instanceId": str(uuid.uuid4()),
                     "integration": "WHATSAPP-BAILEYS", "status": "connecting"},
        "hash": token,
        "qrcode": {"pairingCode": None, "code": "raw-code", "base64": "data:image/png;base64,AAAA"},
    }
    return httpx.Response(201, json=body, request=httpx.Request("POST", "https://x/instance/create"))


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


# ── provision_evolution_channel ─────────────────────────────────────────────


class TestProvisionEvolutionChannel:
    def test_success_creates_channel_and_credential(self, db: Session):
        ws, agent = _make_workspace_and_agent(db)

        with patch(_SETTINGS_PATCH, _mock_settings()), \
             patch("app.services.crypto_service.settings.app_encryption_key", _TEST_ENCRYPTION_KEY):
            with patch("httpx.post") as mock_post:
                mock_post.side_effect = [
                    _create_instance_response("wenzap-xxxx"),  # /instance/create
                    httpx.Response(200, json={"enabled": True},
                                    request=httpx.Request("POST", "https://x/webhook/set")),
                ]
                channel_out, qrcode_base64, pairing_code = svc.provision_evolution_channel(
                    db, ws.id, agent.id
                )

        assert qrcode_base64 == "data:image/png;base64,AAAA"
        assert pairing_code is None
        assert channel_out.channel_type == "whatsapp"
        assert channel_out.config["provider"] == "evolution_api"
        assert channel_out.config["api_key_ref"].startswith("db:")

        cred = db.scalar(
            select(ChannelCredential).where(ChannelCredential.channel_id == channel_out.id)
        )
        assert cred is not None
        assert cred.provider == "evolution_api"
        assert cred.encrypted_value != "INSTANCE_TOKEN_1"  # actually encrypted, not plaintext

    def test_webhook_failure_does_not_fail_provisioning(self, db: Session):
        """Webhook registration is best-effort — a failure must not block channel creation."""
        ws, agent = _make_workspace_and_agent(db)

        with patch(_SETTINGS_PATCH, _mock_settings()), \
             patch("app.services.crypto_service.settings.app_encryption_key", _TEST_ENCRYPTION_KEY):
            with patch("httpx.post") as mock_post:
                mock_post.side_effect = [
                    _create_instance_response("wenzap-yyyy"),
                    httpx.ConnectError("webhook server unreachable"),
                ]
                channel_out, qrcode_base64, _ = svc.provision_evolution_channel(db, ws.id, agent.id)

        assert channel_out is not None
        assert qrcode_base64 == "data:image/png;base64,AAAA"

    def test_missing_master_config_raises_500(self, db: Session):
        ws, agent = _make_workspace_and_agent(db)
        with patch(_SETTINGS_PATCH, _mock_settings(evolution_master_api_key="")):
            with pytest.raises(Exception) as exc_info:
                svc.provision_evolution_channel(db, ws.id, agent.id)
        assert getattr(exc_info.value, "status_code", None) == 500

    def test_create_instance_http_error_raises_502(self, db: Session):
        ws, agent = _make_workspace_and_agent(db)
        with patch(_SETTINGS_PATCH, _mock_settings()):
            with patch("httpx.post", side_effect=httpx.ConnectError("down")):
                with pytest.raises(Exception) as exc_info:
                    svc.provision_evolution_channel(db, ws.id, agent.id)
        assert getattr(exc_info.value, "status_code", None) == 502


# ── check_evolution_connection_status ───────────────────────────────────────


class TestCheckConnectionStatus:
    def test_open_state_marks_channel_active(self, db: Session, monkeypatch):
        ws, agent = _make_workspace_and_agent(db)
        monkeypatch.setenv("EVO_PROV_TEST_KEY", "the-instance-token")
        channel = _make_channel(db, ws, agent)
        channel.config_json = {**channel.config_json, "api_key_ref": "env:EVO_PROV_TEST_KEY"}
        db.commit()

        instance_data = {"instanceName": channel.config_json["instance_name"], "state": "open"}
        resp = httpx.Response(
            200, json={"instance": instance_data},
            request=httpx.Request("GET", "https://x"),
        )
        with patch("httpx.get", return_value=resp):
            state = svc.check_evolution_connection_status(db, channel)

        assert state == "open"
        db.refresh(channel)
        assert channel.config_json["status"] == "active"
        assert channel.config_json["connected_at"] is not None

    def test_connecting_state_does_not_mark_active(self, db: Session, monkeypatch):
        ws, agent = _make_workspace_and_agent(db)
        monkeypatch.setenv("EVO_PROV_TEST_KEY2", "the-instance-token")
        channel = _make_channel(db, ws, agent)
        channel.config_json = {**channel.config_json, "api_key_ref": "env:EVO_PROV_TEST_KEY2"}
        db.commit()

        instance_data = {
            "instanceName": channel.config_json["instance_name"], "state": "connecting"
        }
        resp = httpx.Response(
            200, json={"instance": instance_data},
            request=httpx.Request("GET", "https://x"),
        )
        with patch("httpx.get", return_value=resp):
            state = svc.check_evolution_connection_status(db, channel)

        assert state == "connecting"
        db.refresh(channel)
        assert channel.config_json["status"] == "testing"


# ── disconnect_evolution_channel ────────────────────────────────────────────


class TestDisconnectEvolutionChannel:
    def test_archives_channel_and_calls_delete(self, db: Session):
        ws, agent = _make_workspace_and_agent(db)
        channel = _make_channel(db, ws, agent)

        with patch(_SETTINGS_PATCH, _mock_settings()):
            with patch("httpx.delete") as mock_delete:
                mock_delete.return_value = httpx.Response(
                    200, json={"status": "SUCCESS"}, request=httpx.Request("DELETE", "https://x")
                )
                svc.disconnect_evolution_channel(db, channel)

        db.refresh(channel)
        assert channel.status == "archived"
        mock_delete.assert_called_once()

    def test_archives_channel_even_if_delete_fails(self, db: Session):
        """Best-effort: Evolution-side failure must not block archiving."""
        ws, agent = _make_workspace_and_agent(db)
        channel = _make_channel(db, ws, agent)

        with patch(_SETTINGS_PATCH, _mock_settings()):
            with patch("httpx.delete", side_effect=httpx.ConnectError("down")):
                svc.disconnect_evolution_channel(db, channel)

        db.refresh(channel)
        assert channel.status == "archived"

    def test_noop_delete_call_when_instance_name_missing(self, db: Session):
        ws, agent = _make_workspace_and_agent(db)
        channel = _make_channel(db, ws, agent)
        channel.config_json = {**channel.config_json, "instance_name": None}
        db.commit()

        with patch("httpx.delete") as mock_delete:
            svc.disconnect_evolution_channel(db, channel)

        mock_delete.assert_not_called()
        db.refresh(channel)
        assert channel.status == "archived"
