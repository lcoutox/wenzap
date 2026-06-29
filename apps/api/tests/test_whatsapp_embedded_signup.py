"""
Tests for WhatsApp Embedded Signup — ES.2.

Covers:
  State endpoint
  - generates a valid state token
  - rejects agent from another workspace
  - rejects nonexistent agent
  - viewer role cannot generate state (403)

  State verification helpers (unit)
  - valid state verifies and returns payload
  - invalid signature rejected
  - expired state rejected
  - wrong user_id rejected
  - wrong workspace_id rejected

  Exchange endpoint
  - success: creates channel with db: credential ref
  - success: token not in channel config
  - success: credential encrypted_value != plain token
  - success: display_phone_number saved
  - success: phone_number_id saved in config
  - success: waba_id saved in config
  - success: auto_reply_enabled defaults to false
  - success: updates existing channel instead of creating duplicate
  - conflict: same phone_number_id in another workspace returns 409
  - invalid state signature returns 400
  - expired state returns 400
  - Meta token exchange failure returns 502
  - long-lived token exchange failure returns 502
  - phone_number_id not in WABA returns 422
  - META_APP_ID/SECRET missing returns 503
"""

import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.main import app
from app.models.agent import Agent
from app.models.channel import Channel
from app.models.user import User
from app.models.workspace import Workspace
from app.services.whatsapp_embedded_signup_service import (
    create_embedded_signup_state,
    verify_embedded_signup_state,
)

# ── Fixture key ────────────────────────────────────────────────────────────────

_TEST_KEY = Fernet.generate_key().decode()

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_agent(db: Session, workspace_id: uuid.UUID, name: str = "Agent") -> Agent:
    agent = Agent(workspace_id=workspace_id, name=name, status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_wa_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    phone_number_id: str = "111222333",
    access_token_ref: str = "env:WA_TOKEN",
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="WA",
        public_key=f"wap_{uuid.uuid4().hex[:18]}",
        status="active",
        config_json={
            "provider": "meta_cloud_api",
            "onboarding_type": "manual",
            "waba_id": "999888777",
            "phone_number_id": phone_number_id,
            "access_token_ref": access_token_ref,
        },
    )
    db.add(ch)
    db.flush()
    return ch


@contextmanager
def _client(db: Session, user: User, workspace: Workspace):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    try:
        yield TestClient(app, raise_server_exceptions=True)
    finally:
        app.dependency_overrides.clear()


def _meta_phone_numbers(phone_number_id: str, display: str = "+55 11 91234-5678") -> list[dict]:
    return [
        {
            "id": phone_number_id,
            "display_phone_number": display,
            "verified_name": "Nexbrain Test",
            "status": "CONNECTED",
            "quality_rating": "GREEN",
        }
    ]


# ── State endpoint ─────────────────────────────────────────────────────────────


class TestStateEndpoint:
    def test_generates_state_for_valid_agent(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        with _client(db, user_a, workspace_a) as client:
            with patch("app.services.whatsapp_embedded_signup_service.settings") as ms:
                ms.app_encryption_key = _TEST_KEY
                ms.meta_app_id = "app_id"
                ms.meta_app_secret = "secret"
                ms.meta_graph_api_version = "v25.0"
                resp = client.post(
                    "/channels/whatsapp/embedded-signup/state",
                    json={"agent_id": str(agent.id)},
                )
        assert resp.status_code == 200
        body = resp.json()
        assert "state" in body
        assert body["expires_in"] == 600

    def test_rejects_agent_from_other_workspace(
        self, db: Session, user_a: User, workspace_a: Workspace,
        workspace_b: Workspace, user_b: User
    ):
        agent_b = _make_agent(db, workspace_b.id)
        with _client(db, user_a, workspace_a) as client:
            with patch("app.services.whatsapp_embedded_signup_service.settings") as ms:
                ms.app_encryption_key = _TEST_KEY
                resp = client.post(
                    "/channels/whatsapp/embedded-signup/state",
                    json={"agent_id": str(agent_b.id)},
                )
        assert resp.status_code == 404

    def test_rejects_nonexistent_agent(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        with _client(db, user_a, workspace_a) as client:
            with patch("app.services.whatsapp_embedded_signup_service.settings") as ms:
                ms.app_encryption_key = _TEST_KEY
                resp = client.post(
                    "/channels/whatsapp/embedded-signup/state",
                    json={"agent_id": str(uuid.uuid4())},
                )
        assert resp.status_code == 404

    def test_viewer_cannot_generate_state(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        from app.enums import MemberRole, MemberStatus
        from app.models.workspace_member import WorkspaceMember
        # Add a viewer member to workspace_a
        viewer = User(
            email="viewer@test.com",
            name="Viewer",
        )
        db.add(viewer)
        db.flush()
        member = WorkspaceMember(
            workspace_id=workspace_a.id,
            user_id=viewer.id,
            role=MemberRole.viewer,
            status=MemberStatus.active,
        )
        db.add(member)
        db.flush()

        agent = _make_agent(db, workspace_a.id)
        with _client(db, viewer, workspace_a) as client:
            with patch("app.services.whatsapp_embedded_signup_service.settings") as ms:
                ms.app_encryption_key = _TEST_KEY
                resp = client.post(
                    "/channels/whatsapp/embedded-signup/state",
                    json={"agent_id": str(agent.id)},
                )
        assert resp.status_code == 403


# ── State helper unit tests ────────────────────────────────────────────────────


class TestStateHelpers:
    def _patch_key(self):
        return patch(
            "app.services.whatsapp_embedded_signup_service.settings",
            **{"app_encryption_key": _TEST_KEY},
        )

    def test_valid_state_verifies(self):
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        agent_id = uuid.uuid4()
        with self._patch_key():
            token = create_embedded_signup_state(user_id, workspace_id, agent_id)
            payload = verify_embedded_signup_state(token, user_id, workspace_id)
        assert payload["a"] == str(agent_id)

    def test_tampered_signature_rejected(self):
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        with self._patch_key():
            token = create_embedded_signup_state(user_id, workspace_id, uuid.uuid4())
            tampered = token[:-4] + "xxxx"
            with pytest.raises(Exception) as exc_info:
                verify_embedded_signup_state(tampered, user_id, workspace_id)
        assert "invalid_state" in str(exc_info.value.detail)

    def test_expired_state_rejected(self):
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        import hashlib
        import hmac as _hmac
        import json
        import secrets

        # Manually build an expired token
        key_str = _TEST_KEY
        signing_key = hashlib.sha256(f"nexbrain-signup-state:{key_str}".encode()).digest()
        past = int((datetime.now(timezone.utc) - timedelta(seconds=1)).timestamp())
        payload = json.dumps(
            {
                "u": str(user_id),
                "w": str(workspace_id),
                "a": str(uuid.uuid4()),
                "exp": past,
                "nonce": secrets.token_hex(8),
            },
            separators=(",", ":"),
        )
        payload_b64 = payload.encode().hex()
        sig = _hmac.new(signing_key, payload_b64.encode(), hashlib.sha256).hexdigest()
        expired_token = f"{payload_b64}.{sig}"

        with patch(
            "app.services.whatsapp_embedded_signup_service.settings",
            **{"app_encryption_key": _TEST_KEY},
        ):
            with pytest.raises(Exception) as exc_info:
                verify_embedded_signup_state(expired_token, user_id, workspace_id)
        assert "expired_state" in str(exc_info.value.detail)

    def test_wrong_user_id_rejected(self):
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        with self._patch_key():
            token = create_embedded_signup_state(user_id, workspace_id, uuid.uuid4())
            with pytest.raises(Exception) as exc_info:
                verify_embedded_signup_state(token, uuid.uuid4(), workspace_id)
        assert "invalid_state" in str(exc_info.value.detail)

    def test_wrong_workspace_id_rejected(self):
        user_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        with self._patch_key():
            token = create_embedded_signup_state(user_id, workspace_id, uuid.uuid4())
            with pytest.raises(Exception) as exc_info:
                verify_embedded_signup_state(token, user_id, uuid.uuid4())
        assert "invalid_state" in str(exc_info.value.detail)


# ── Exchange endpoint ──────────────────────────────────────────────────────────


def _valid_state(user_id: uuid.UUID, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> str:
    with patch(
        "app.services.whatsapp_embedded_signup_service.settings",
        **{"app_encryption_key": _TEST_KEY},
    ):
        return create_embedded_signup_state(user_id, workspace_id, agent_id)


@contextmanager
def _patch_settings(extra: dict | None = None):
    """
    Patch settings in both whatsapp_embedded_signup_service and crypto_service
    so that APP_ENCRYPTION_KEY is visible to Fernet operations during tests.
    """
    attrs = {
        "app_encryption_key": _TEST_KEY,
        "meta_app_id": "test_app_id",
        "meta_app_secret": "test_app_secret",
        "meta_graph_api_version": "v25.0",
    }
    if extra:
        attrs.update(extra)
    with patch("app.services.whatsapp_embedded_signup_service.settings", **attrs):
        with patch("app.services.crypto_service.settings", **attrs):
            yield


def _mock_httpx_success(
    short_lived: str = "short_token",
    long_lived: str = "long_token",
    expires_in: int = 5184000,
    phone_number_id: str = "111222333",
    display_phone: str = "+55 11 91234-5678",
):
    """Return a side_effect callable that mocks httpx.get for 3 consecutive calls."""
    def _ok(data: dict) -> MagicMock:
        m = MagicMock()
        m.json.return_value = data
        m.raise_for_status.return_value = None
        return m

    responses = [
        _ok({"access_token": short_lived}),
        _ok({"access_token": long_lived, "expires_in": expires_in}),
        _ok({"data": _meta_phone_numbers(phone_number_id, display_phone)}),
    ]
    call_count = [0]

    def _side_effect(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        return responses[idx]

    return _side_effect


def _mock_meta(phone_number_id: str = "111222333", **kwargs):
    """Shorthand: patch httpx.get with default success side_effect."""
    effect = _mock_httpx_success(phone_number_id=phone_number_id, **kwargs)
    return patch("httpx.get", side_effect=effect)


class TestExchangeEndpoint:
    _WA_ID = "444555666"
    _PHONE_ID = "111222333"
    _DISPLAY = "+55 11 91234-5678"

    def _do_exchange(
        self,
        client: TestClient,
        state: str,
        waba_id: str = _WA_ID,
        phone_number_id: str = _PHONE_ID,
        code: str = "auth_code_from_meta",
    ):
        return client.post(
            "/channels/whatsapp/embedded-signup/exchange",
            json={
                "code": code,
                "state": state,
                "waba_id": waba_id,
                "phone_number_id": phone_number_id,
            },
        )

    def test_creates_channel_success(self, db: Session, user_a: User, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID):
                    resp = self._do_exchange(client, state)

        assert resp.status_code == 201
        body = resp.json()
        assert body["channel_type"] == "whatsapp"
        assert body["config"]["waba_id"] == self._WA_ID
        assert body["config"]["phone_number_id"] == self._PHONE_ID

    def test_access_token_ref_is_db(self, db: Session, user_a: User, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID):
                    resp = self._do_exchange(client, state)

        config = resp.json()["config"]
        assert config["access_token_ref"].startswith("db:")

    def test_plain_token_not_in_config(self, db: Session, user_a: User, workspace_a: Workspace):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)
        plain_token = "super-secret-long-lived-token"

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID, long_lived=plain_token):
                    resp = self._do_exchange(client, state)

        config_str = str(resp.json()["config"])
        assert plain_token not in config_str

    def test_credential_encrypted_value_differs_from_plain(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        from sqlalchemy import select

        from app.models.channel_credential import ChannelCredential

        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)
        plain_token = "plaintext-token-xyz"

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID, long_lived=plain_token):
                    resp = self._do_exchange(client, state)

        assert resp.status_code == 201
        cred = db.scalar(select(ChannelCredential).where(
            ChannelCredential.workspace_id == workspace_a.id,
            ChannelCredential.credential_type == "whatsapp_user_access_token",
        ))
        assert cred is not None
        assert cred.encrypted_value != plain_token
        assert plain_token not in cred.encrypted_value

    def test_display_phone_number_saved(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID, display_phone=self._DISPLAY):
                    resp = self._do_exchange(client, state)

        assert resp.json()["config"]["display_phone_number"] == self._DISPLAY

    def test_auto_reply_enabled_defaults_false(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID):
                    resp = self._do_exchange(client, state)

        assert resp.json()["config"]["auto_reply_enabled"] is False

    def test_updates_existing_channel_same_workspace(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_wa_channel(db, workspace_a.id, agent.id, phone_number_id=self._PHONE_ID)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID):
                    resp = self._do_exchange(client, state)

        assert resp.status_code == 201
        # Only one channel should exist for this phone number
        from sqlalchemy import select as sa_select
        count = db.execute(
            sa_select(Channel).where(
                Channel.workspace_id == workspace_a.id,
                Channel.channel_type == "whatsapp",
                Channel.config_json["phone_number_id"].astext == self._PHONE_ID,
            )
        ).scalars().all()
        assert len(count) == 1

    def test_conflict_same_phone_number_other_workspace(
        self, db: Session, user_a: User, workspace_a: Workspace,
        user_b: User, workspace_b: Workspace
    ):
        agent_b = _make_agent(db, workspace_b.id)
        # workspace_b already has this phone number
        _make_wa_channel(db, workspace_b.id, agent_b.id, phone_number_id=self._PHONE_ID)
        db.commit()

        agent_a = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent_a.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta(self._PHONE_ID):
                    resp = self._do_exchange(client, state)

        assert resp.status_code == 409
        assert "whatsapp_number_already_connected" in resp.json()["detail"]

    def test_invalid_state_signature_rejected(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)
        bad_state = state[:-4] + "xxxx"

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                resp = self._do_exchange(client, bad_state)

        assert resp.status_code == 400
        assert "invalid_state" in resp.json()["detail"]

    def test_expired_state_rejected(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        import hashlib
        import hmac as _hmac
        import json
        import secrets as _secrets

        signing_key = hashlib.sha256(f"nexbrain-signup-state:{_TEST_KEY}".encode()).digest()
        past = int((datetime.now(timezone.utc) - timedelta(seconds=1)).timestamp())
        agent = _make_agent(db, workspace_a.id)
        payload = json.dumps(
            {"u": str(user_a.id), "w": str(workspace_a.id), "a": str(agent.id),
             "exp": past, "nonce": _secrets.token_hex(8)},
            separators=(",", ":"),
        )
        payload_b64 = payload.encode().hex()
        sig = _hmac.new(signing_key, payload_b64.encode(), hashlib.sha256).hexdigest()
        expired_state = f"{payload_b64}.{sig}"

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                resp = self._do_exchange(client, expired_state)

        assert resp.status_code == 400
        assert "expired_state" in resp.json()["detail"]

    def test_meta_token_exchange_failure_returns_502(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        import httpx as _httpx

        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.json.return_value = {"error": {"message": "Invalid code"}}
        error_resp.text = "bad request"

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with patch("httpx.get", side_effect=_httpx.HTTPStatusError(
                    "bad", request=MagicMock(), response=error_resp
                )):
                    resp = self._do_exchange(client, state)

        assert resp.status_code == 502
        assert resp.json()["detail"] == "meta_token_exchange_failed"

    def test_long_lived_exchange_failure_returns_502(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        import httpx as _httpx

        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        short_ok = MagicMock()
        short_ok.json.return_value = {"access_token": "short"}
        short_ok.raise_for_status.return_value = None
        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.json.return_value = {"error": {"message": "Token exchange failed"}}
        error_resp.text = "bad"

        call_count = [0]
        def _side_effect(*args, **kwargs):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                return short_ok
            raise _httpx.HTTPStatusError("bad", request=MagicMock(), response=error_resp)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with patch("httpx.get", side_effect=_side_effect):
                    resp = self._do_exchange(client, state)

        assert resp.status_code == 502
        assert resp.json()["detail"] == "meta_token_exchange_failed"

    def test_phone_number_not_in_waba_returns_422(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        # WABA returns a different phone_number_id than what frontend sent
        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with _mock_meta("DIFFERENT_ID"):
                    resp = self._do_exchange(client, state, phone_number_id=self._PHONE_ID)

        assert resp.status_code == 422
        assert resp.json()["detail"] == "phone_number_not_found"

    def test_meta_config_missing_returns_503(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings({"meta_app_id": "", "meta_app_secret": ""}):
                resp = self._do_exchange(client, state)

        assert resp.status_code == 503
        assert resp.json()["detail"] == "meta_config_missing"

    def test_exchange_requires_waba_id(self, db: Session, user_a: User, workspace_a: Workspace):
        """Exchange endpoint rejects requests without waba_id."""
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                resp = client.post(
                    "/channels/whatsapp/embedded-signup/exchange",
                    json={"code": "auth_code", "state": state, "phone_number_id": self._PHONE_ID},
                )

        assert resp.status_code == 422  # missing required field

    def test_exchange_requires_phone_number_id(self, db: Session, user_a: User, workspace_a: Workspace):
        """Exchange endpoint rejects requests without phone_number_id."""
        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                resp = client.post(
                    "/channels/whatsapp/embedded-signup/exchange",
                    json={"code": "auth_code", "state": state, "waba_id": self._WA_ID},
                )

        assert resp.status_code == 422  # missing required field

    def test_code_exchanged_without_redirect_uri(self, db: Session, user_a: User, workspace_a: Workspace):
        """Verify the Meta code exchange call does not include redirect_uri."""

        agent = _make_agent(db, workspace_a.id)
        state = _valid_state(user_a.id, workspace_a.id, agent.id)
        captured_params: list[dict] = []

        def _ok(data: dict) -> MagicMock:
            m = MagicMock()
            m.json.return_value = data
            m.raise_for_status.return_value = None
            return m

        responses = [
            _ok({"access_token": "short"}),
            _ok({"access_token": "long", "expires_in": 5184000}),
            _ok({"data": _meta_phone_numbers(self._PHONE_ID, self._DISPLAY)}),
        ]
        call_count = [0]

        def _side_effect(*args, **kwargs):
            captured_params.append(kwargs.get("params", {}))
            idx = call_count[0]
            call_count[0] += 1
            return responses[idx]

        with _client(db, user_a, workspace_a) as client:
            with _patch_settings():
                with patch("httpx.get", side_effect=_side_effect):
                    resp = self._do_exchange(client, state)

        assert resp.status_code == 201
        # First call is the code exchange — must not include redirect_uri
        code_exchange_params = captured_params[0]
        assert "redirect_uri" not in code_exchange_params
