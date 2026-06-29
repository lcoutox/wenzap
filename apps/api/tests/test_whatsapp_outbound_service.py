"""
Tests for whatsapp_outbound_service.py — Phase 6.3-A.

Unit tests: no real HTTP calls. httpx is monkeypatched throughout.

Covers:
  normalize_whatsapp_to
  - extracts number from external_id "whatsapp:..."
  - fallback to phone field (strips +)
  - returns None when both are absent
  - returns None when external_id present but not whatsapp prefix

  _resolve_access_token
  - resolves "env:VAR" when var is set
  - returns None when env var is missing
  - returns None when access_token_ref is absent

  deliver_human_message — channel not found
  - saves delivery failed with error_code channel_not_found

  deliver_human_message — missing recipient
  - saves delivery failed with error_code missing_recipient

  deliver_human_message — missing token
  - saves delivery failed with error_code missing_token

  deliver_human_message — Meta HTTP 400
  - saves delivery failed with error_code http_error

  deliver_human_message — timeout
  - saves delivery failed with error_code timeout

  deliver_human_message — request error
  - saves delivery failed with error_code request_error

  deliver_human_message — response missing wamid
  - saves delivery failed with error_code missing_wamid

  deliver_human_message — success
  - calls Meta with correct URL
  - calls Meta with correct Authorization header
  - calls Meta with correct JSON payload (messaging_product, to, type, text.body)
  - saves external_message_id = wamid
  - saves metadata_json.delivery.status = "sent"
  - preserves existing metadata_json fields

  deliver_human_message — unexpected exception
  - does not raise
  - saves delivery failed with error_code unexpected_error
"""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.whatsapp_outbound_service import (
    deliver_human_message,
    normalize_whatsapp_to,
)

# ── Helpers — plain SimpleNamespace objects (no SQLAlchemy mapper needed) ──────


def _contact(external_id: str | None = None, phone: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        name="Test",
        external_id=external_id,
        phone=phone,
    )


def _channel(
    phone_number_id: str = "PID_123",
    access_token_ref: str | None = "env:WHATSAPP_TEMP_ACCESS_TOKEN",
    status: str = "active",
    channel_type: str = "whatsapp",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        channel_type=channel_type,
        status=status,
        config_json={
            "phone_number_id": phone_number_id,
            "access_token_ref": access_token_ref,
        },
    )


def _conversation(
    channel_type: str = "whatsapp",
    channel_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        channel_type=channel_type,
        channel_id=channel_id,
        contact_id=contact_id or uuid.uuid4(),
        agent_id=agent_id or uuid.uuid4(),
    )


def _message(
    content: str = "Olá",
    direction: str = "outbound",
    sender_type: str = "human",
    metadata_json: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        direction=direction,
        sender_type=sender_type,
        content=content,
        external_message_id=None,
        metadata_json=metadata_json,
    )


def _mock_db(channel=None, contact=None) -> MagicMock:
    """
    Fake DB session for unit tests.

    db.get() dispatches by primary key value:
      - matches channel.id → returns channel
      - matches contact.id → returns contact

    db.scalar() returns channel (used by the fallback workspace+agent lookup).
    """
    db = MagicMock()

    def _db_get(_model, pk):
        if channel is not None and pk == channel.id:
            return channel
        if contact is not None and pk == contact.id:
            return contact
        return None

    db.get.side_effect = _db_get
    db.scalar.return_value = channel
    return db


def _meta_success_response(wamid: str = "wamid.OUT001") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"messages": [{"id": wamid}]}
    resp.raise_for_status.return_value = None
    return resp


# ── normalize_whatsapp_to ──────────────────────────────────────────────────────


class TestNormalizeWhatsappTo:
    def test_extracts_from_external_id(self):
        result = normalize_whatsapp_to(_contact(external_id="whatsapp:5537999999999"))
        assert result == "5537999999999"

    def test_fallback_to_phone_strips_plus(self):
        assert normalize_whatsapp_to(_contact(phone="+5511988887777")) == "5511988887777"

    def test_phone_without_plus(self):
        assert normalize_whatsapp_to(_contact(phone="5511988887777")) == "5511988887777"

    def test_returns_none_when_both_absent(self):
        assert normalize_whatsapp_to(_contact()) is None

    def test_returns_none_when_external_id_not_whatsapp(self):
        assert normalize_whatsapp_to(_contact(external_id="instagram:user123")) is None

    def test_prefers_external_id_over_phone(self):
        c = _contact(external_id="whatsapp:5537000000001", phone="+5537000000002")
        assert normalize_whatsapp_to(c) == "5537000000001"

    def test_returns_none_when_external_id_is_just_prefix(self):
        # "whatsapp:" with empty wa_id
        assert normalize_whatsapp_to(_contact(external_id="whatsapp:")) is None


# ── _resolve_access_token (via deliver path) ───────────────────────────────────


class TestResolveAccessToken:
    def test_resolves_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_abc123")
        ch = _channel(access_token_ref="env:WHATSAPP_TEMP_ACCESS_TOKEN")
        contact = _contact(external_id="whatsapp:5511000000001")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        with patch("httpx.post", return_value=_meta_success_response()) as mock_post:
            deliver_human_message(db, msg, conv)

        call_kwargs = mock_post.call_args
        assert "Bearer tok_abc123" in call_kwargs.kwargs["headers"]["Authorization"]

    def test_returns_failed_when_env_var_missing(self, monkeypatch):
        monkeypatch.delenv("WHATSAPP_TEMP_ACCESS_TOKEN", raising=False)
        ch = _channel(access_token_ref="env:WHATSAPP_TEMP_ACCESS_TOKEN")
        contact = _contact(external_id="whatsapp:5511000000002")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        with patch("httpx.post") as mock_post:
            deliver_human_message(db, msg, conv)

        mock_post.assert_not_called()
        assert msg.metadata_json["delivery"]["error_type"] == "missing_token"

    def test_returns_failed_when_access_token_ref_absent(self):
        ch = _channel(access_token_ref=None)
        contact = _contact(external_id="whatsapp:5511000000003")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        with patch("httpx.post") as mock_post:
            deliver_human_message(db, msg, conv)

        mock_post.assert_not_called()
        assert msg.metadata_json["delivery"]["error_type"] == "missing_token"


# ── deliver_human_message — failure modes ─────────────────────────────────────


class TestDeliverHumanMessageFailures:
    def test_channel_not_found_saves_failed(self):
        conv = _conversation()
        conv.channel_id = None
        msg = _message()
        db = MagicMock()
        db.get.return_value = None
        db.scalar.return_value = None

        deliver_human_message(db, msg, conv)

        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "failed"
        assert delivery["error_type"] == "channel_not_found"
        assert delivery["channel"] == "whatsapp"
        assert delivery["provider"] == "meta_cloud_api"
        assert "failed_at" in delivery

    def test_missing_recipient_saves_failed(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_abc")
        ch = _channel()
        contact = _contact()  # no external_id, no phone
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        with patch("httpx.post") as mock_post:
            deliver_human_message(db, msg, conv)

        mock_post.assert_not_called()
        assert msg.metadata_json["delivery"]["error_type"] == "missing_recipient"

    def test_missing_token_saves_failed(self, monkeypatch):
        monkeypatch.delenv("WHATSAPP_TEMP_ACCESS_TOKEN", raising=False)
        ch = _channel(access_token_ref="env:WHATSAPP_TEMP_ACCESS_TOKEN")
        contact = _contact(external_id="whatsapp:5511999111222")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        deliver_human_message(db, msg, conv)

        assert msg.metadata_json["delivery"]["error_type"] == "missing_token"

    def test_http_400_saves_failed_with_status(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_abc")
        ch = _channel()
        contact = _contact(external_id="whatsapp:5511999111333")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        http_resp = MagicMock()
        http_resp.status_code = 400
        http_resp.text = "Bad Request"
        http_resp.json.return_value = {}
        exc = httpx.HTTPStatusError("400", request=MagicMock(), response=http_resp)
        with patch("httpx.post", side_effect=exc):
            deliver_human_message(db, msg, conv)

        delivery = msg.metadata_json["delivery"]
        assert delivery["status"] == "failed"
        assert delivery["error_type"] == "http_error"
        assert delivery["error_status"] == 400
        assert "failed_at" in delivery

    def test_http_401_saves_error_status_401(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_expired")
        ch = _channel()
        contact = _contact(external_id="whatsapp:5511999111334")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        http_resp = MagicMock()
        http_resp.status_code = 401
        http_resp.text = "Unauthorized"
        http_resp.json.return_value = {"error": {"message": "Invalid OAuth access token."}}
        exc = httpx.HTTPStatusError("401", request=MagicMock(), response=http_resp)
        with patch("httpx.post", side_effect=exc):
            deliver_human_message(db, msg, conv)

        delivery = msg.metadata_json["delivery"]
        assert delivery["error_type"] == "http_error"
        assert delivery["error_status"] == 401
        assert delivery["error_message"] == "Invalid OAuth access token."

    def test_timeout_saves_failed(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_abc")
        ch = _channel()
        contact = _contact(external_id="whatsapp:5511999111444")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")):
            deliver_human_message(db, msg, conv)

        assert msg.metadata_json["delivery"]["error_type"] == "timeout"

    def test_request_error_saves_failed(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_abc")
        ch = _channel()
        contact = _contact(external_id="whatsapp:5511999111555")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        with patch("httpx.post", side_effect=httpx.ConnectError("conn refused")):
            deliver_human_message(db, msg, conv)

        assert msg.metadata_json["delivery"]["error_type"] == "request_error"

    def test_response_missing_wamid_saves_failed(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_abc")
        ch = _channel()
        contact = _contact(external_id="whatsapp:5511999111666")
        conv = _conversation(channel_id=ch.id, contact_id=contact.id)
        msg = _message()
        db = _mock_db(channel=ch, contact=contact)

        resp = MagicMock()
        resp.json.return_value = {"messages": [{}]}  # id missing
        resp.raise_for_status.return_value = None
        with patch("httpx.post", return_value=resp):
            deliver_human_message(db, msg, conv)

        assert msg.metadata_json["delivery"]["error_type"] == "missing_wamid"

    def test_unexpected_exception_does_not_raise(self):
        conv = _conversation()
        msg = _message()
        db = MagicMock()
        db.get.side_effect = RuntimeError("boom")

        # Must not raise.
        deliver_human_message(db, msg, conv)

        assert msg.metadata_json["delivery"]["error_type"] == "unexpected_error"


# ── deliver_human_message — success ───────────────────────────────────────────


class TestDeliverHumanMessageSuccess:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_TEMP_ACCESS_TOKEN", "tok_valid_abc")
        self.ch = _channel(phone_number_id="PID_OUT_PROD")
        self.contact = _contact(external_id="whatsapp:5537888777666")
        self.conv = _conversation(channel_id=self.ch.id, contact_id=self.contact.id)
        self.msg = _message(content="Boa tarde, como posso ajudar?")
        self.db = _mock_db(channel=self.ch, contact=self.contact)

    def test_calls_meta_with_correct_url(self):
        with patch("httpx.post", return_value=_meta_success_response()) as mock_post:
            deliver_human_message(self.db, self.msg, self.conv)
        url = mock_post.call_args.args[0]
        assert url == "https://graph.facebook.com/v21.0/PID_OUT_PROD/messages"

    def test_calls_meta_with_authorization_header(self):
        with patch("httpx.post", return_value=_meta_success_response()) as mock_post:
            deliver_human_message(self.db, self.msg, self.conv)
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer tok_valid_abc"

    def test_calls_meta_with_correct_payload(self):
        with patch("httpx.post", return_value=_meta_success_response()) as mock_post:
            deliver_human_message(self.db, self.msg, self.conv)
        payload = mock_post.call_args.kwargs["json"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "5537888777666"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Boa tarde, como posso ajudar?"

    def test_saves_external_message_id(self):
        with patch("httpx.post", return_value=_meta_success_response("wamid.OUT_SUCCESS_001")):
            deliver_human_message(self.db, self.msg, self.conv)
        assert self.msg.external_message_id == "wamid.OUT_SUCCESS_001"

    def test_saves_delivery_status_sent(self):
        with patch("httpx.post", return_value=_meta_success_response("wamid.SENT_01")):
            deliver_human_message(self.db, self.msg, self.conv)
        delivery = self.msg.metadata_json["delivery"]
        assert delivery["status"] == "sent"
        assert delivery["channel"] == "whatsapp"
        assert delivery["provider"] == "meta_cloud_api"
        assert delivery["external_message_id"] == "wamid.SENT_01"
        assert delivery["phone_number_id"] == "PID_OUT_PROD"
        assert delivery["recipient"] == "5537888777666"
        assert "sent_at" in delivery

    def test_preserves_existing_metadata_json(self):
        self.msg.metadata_json = {"custom_field": "keep_me"}
        with patch("httpx.post", return_value=_meta_success_response()):
            deliver_human_message(self.db, self.msg, self.conv)
        assert self.msg.metadata_json["custom_field"] == "keep_me"
        assert self.msg.metadata_json["delivery"]["status"] == "sent"

    def test_commits_after_success(self):
        with patch("httpx.post", return_value=_meta_success_response()):
            deliver_human_message(self.db, self.msg, self.conv)
        self.db.commit.assert_called()

    def test_phone_number_id_in_url(self):
        ch2 = _channel(phone_number_id="DIFFERENT_PID_999")
        contact2 = _contact(external_id="whatsapp:5511000111222")
        conv2 = _conversation(channel_id=ch2.id, contact_id=contact2.id)
        msg2 = _message()
        db2 = _mock_db(channel=ch2, contact=contact2)

        with patch("httpx.post", return_value=_meta_success_response()) as mock_post:
            deliver_human_message(db2, msg2, conv2)

        url = mock_post.call_args.args[0]
        assert "DIFFERENT_PID_999" in url
