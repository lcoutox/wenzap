"""Tests for messaging/evolution_provider.py — Evolution API outbound (bridge provider).

Unit tests: no real HTTP calls. httpx is monkeypatched throughout.
Mirrors test_whatsapp_outbound_service.py's structure for the Meta provider.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.services.messaging.evolution_provider import EvolutionOutboundProvider

# ── Helpers ──────────────────────────────────────────────────────────────────


def _contact(
    external_id: str | None = "whatsapp:5537999999999", phone: str | None = None
) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), workspace_id=uuid.uuid4(), name="Test",
                            external_id=external_id, phone=phone)


def _channel(
    base_url: str = "https://api.wenzap.com.br",
    instance_name: str = "cliente-teste",
    api_key_ref: str | None = "env:EVOLUTION_TEST_API_KEY",
    status: str = "active",
    channel_type: str = "whatsapp",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), agent_id=uuid.uuid4(),
        channel_type=channel_type, status=status,
        config_json={
            "provider": "evolution_api",
            "base_url": base_url,
            "instance_name": instance_name,
            "api_key_ref": api_key_ref,
        },
    )


def _conversation(
    channel_type: str = "whatsapp",
    channel_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), channel_type=channel_type,
        channel_id=channel_id, contact_id=contact_id or uuid.uuid4(),
        agent_id=agent_id or uuid.uuid4(),
    )


def _message(
    content: str = "Olá", metadata_json: dict | None = None, content_type: str = "text"
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), content=content,
        direction="outbound", sender_type="human", content_type=content_type,
        external_message_id=None, metadata_json=metadata_json,
    )


class _FakeDB:
    """Minimal DB double: db.get(Channel, id) and db.scalar(select(...))."""

    def __init__(self, channel: SimpleNamespace | None, contact: SimpleNamespace | None = None):
        self._channel = channel
        self._contact = contact
        self.committed = 0

    def get(self, model, id_):  # noqa: ARG002
        # Distinguish Channel vs Contact lookups by attribute shape is overkill;
        # tests route lookups by conversation.channel_id (Channel) or
        # conversation.contact_id (Contact) — both resolved via this generic get.
        if self._channel is not None and getattr(self._channel, "id", None) == id_:
            return self._channel
        if self._contact is not None and getattr(self._contact, "id", None) == id_:
            return self._contact
        return None

    def scalar(self, _stmt):
        return self._channel

    def commit(self):
        self.committed += 1


def _meta_response(json_body: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(status_code=status_code, json=json_body,
                           request=httpx.Request("POST", "https://api.wenzap.com.br/x"))


_PROVIDER = EvolutionOutboundProvider()
_HTTP_POST = "httpx.post"


# ── channel not found ───────────────────────────────────────────────────────


def test_channel_not_found_saves_failure():
    db = _FakeDB(channel=None)
    msg = _message()
    conv = _conversation(channel_id=None)
    _PROVIDER.deliver(db, msg, conv)
    assert msg.metadata_json["delivery"]["status"] == "failed"
    assert msg.metadata_json["delivery"]["error_type"] == "channel_not_found"
    assert msg.metadata_json["delivery"]["provider"] == "evolution_api"


# ── missing recipient ────────────────────────────────────────────────────────


def test_missing_recipient_saves_failure():
    channel = _channel()
    contact = _contact(external_id=None, phone=None)
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message()
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)
    _PROVIDER.deliver(db, msg, conv)
    assert msg.metadata_json["delivery"]["error_type"] == "missing_recipient"


# ── missing instance config ──────────────────────────────────────────────────


def test_missing_instance_name_saves_failure():
    channel = _channel(instance_name="")
    channel.config_json["instance_name"] = None
    contact = _contact()
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message()
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)
    _PROVIDER.deliver(db, msg, conv)
    assert msg.metadata_json["delivery"]["error_type"] == "missing_instance_config"


# ── missing api key ──────────────────────────────────────────────────────────


def test_missing_api_key_saves_failure(monkeypatch):
    monkeypatch.delenv("EVOLUTION_TEST_API_KEY", raising=False)
    channel = _channel()
    contact = _contact()
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message()
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)
    _PROVIDER.deliver(db, msg, conv)
    assert msg.metadata_json["delivery"]["error_type"] == "missing_api_key"


# ── HTTP error ────────────────────────────────────────────────────────────────


def test_http_error_saves_failure(monkeypatch):
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel()
    contact = _contact()
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message()
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    resp = _meta_response({"message": "instance not found"}, status_code=404)
    with patch(_HTTP_POST, return_value=resp):
        _PROVIDER.deliver(db, msg, conv)

    assert msg.metadata_json["delivery"]["error_type"] == "http_error"
    assert msg.metadata_json["delivery"]["error_status"] == 404


# ── timeout / request error ──────────────────────────────────────────────────


def test_timeout_saves_failure(monkeypatch):
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel()
    contact = _contact()
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message()
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    with patch(_HTTP_POST, side_effect=httpx.TimeoutException("timeout")):
        _PROVIDER.deliver(db, msg, conv)

    assert msg.metadata_json["delivery"]["error_type"] == "timeout"


def test_request_error_saves_failure(monkeypatch):
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel()
    contact = _contact()
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message()
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    with patch(_HTTP_POST, side_effect=httpx.ConnectError("conn refused")):
        _PROVIDER.deliver(db, msg, conv)

    assert msg.metadata_json["delivery"]["error_type"] == "request_error"


# ── success ───────────────────────────────────────────────────────────────────


def test_success_delivers_and_saves_metadata(monkeypatch):
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel(base_url="https://api.wenzap.com.br", instance_name="cliente-teste")
    contact = _contact(external_id="whatsapp:5537999999999")
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message(content="Olá, tudo bem?")
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    resp = _meta_response({"key": {"id": "EVO_MSG_123"}, "status": "PENDING"})
    with patch(_HTTP_POST, return_value=resp) as mock_post:
        _PROVIDER.deliver(db, msg, conv)

    call_args = mock_post.call_args
    assert call_args.args[0] == "https://api.wenzap.com.br/message/sendText/cliente-teste"
    assert call_args.kwargs["json"] == {"number": "5537999999999", "text": "Olá, tudo bem?"}
    assert call_args.kwargs["headers"]["apikey"] == "fake-key"

    delivery = msg.metadata_json["delivery"]
    assert delivery["status"] == "sent"
    assert delivery["provider"] == "evolution_api"
    assert delivery["external_message_id"] == "EVO_MSG_123"
    assert msg.external_message_id == "EVO_MSG_123"
    assert db.committed >= 1


def test_success_without_id_field_still_marks_sent(monkeypatch):
    """Evolution's exact response shape is unconfirmed — a 2xx without a
    recognizable id field should not be treated as a failure."""
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel()
    contact = _contact()
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message()
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    resp = _meta_response({"status": "ok"})
    with patch(_HTTP_POST, return_value=resp):
        _PROVIDER.deliver(db, msg, conv)

    assert msg.metadata_json["delivery"]["status"] == "sent"
    assert msg.metadata_json["delivery"]["external_message_id"] is None


# ── unexpected exception ─────────────────────────────────────────────────────


def test_unexpected_exception_does_not_raise():
    class ExplodingDB(_FakeDB):
        def get(self, model, id_):
            raise RuntimeError("boom")

    db = ExplodingDB(channel=None)
    msg = _message()
    conv = _conversation(channel_id=uuid.uuid4())
    _PROVIDER.deliver(db, msg, conv)  # must not raise
    assert msg.metadata_json["delivery"]["error_type"] == "unexpected_error"


# ── deliver_media (whatsapp-voice-groq-elevenlabs-prd.md) ──────────────────────


def _patched_storage(data: bytes = b"fake-media-bytes"):
    fake_storage = SimpleNamespace(get_file=lambda key: data)  # noqa: ARG005
    return patch(
        "app.services.storage.factory.get_storage_provider", return_value=fake_storage
    )


def test_deliver_media_audio_calls_send_whatsapp_audio(monkeypatch):
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel(base_url="https://api.wenzap.com.br", instance_name="cliente-teste")
    contact = _contact(external_id="whatsapp:5537999999999")
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message(content_type="audio")
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    resp = _meta_response({"key": {"id": "EVO_AUDIO_1"}})
    with _patched_storage(), patch(_HTTP_POST, return_value=resp) as mock_post:
        _PROVIDER.deliver_media(
            db, msg, conv, storage_key="conversation-media/ws/voice.ogg", mime_type="audio/ogg"
        )

    call_args = mock_post.call_args
    assert call_args.args[0] == "https://api.wenzap.com.br/message/sendWhatsAppAudio/cliente-teste"
    assert call_args.kwargs["json"]["number"] == "5537999999999"
    assert call_args.kwargs["json"]["encoding"] is True
    assert msg.metadata_json["delivery"]["status"] == "sent"
    assert msg.metadata_json["delivery"]["external_message_id"] == "EVO_AUDIO_1"


def test_deliver_media_image_calls_send_media_with_caption(monkeypatch):
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel(base_url="https://api.wenzap.com.br", instance_name="cliente-teste")
    contact = _contact(external_id="whatsapp:5537999999999")
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message(content_type="image")
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    resp = _meta_response({"key": {"id": "EVO_IMG_1"}})
    with _patched_storage(), patch(_HTTP_POST, return_value=resp) as mock_post:
        _PROVIDER.deliver_media(
            db, msg, conv,
            storage_key="conversation-media/ws/img.jpg", mime_type="image/jpeg",
            caption="Toyota Corolla — R$ 88.900,00",
        )

    call_args = mock_post.call_args
    assert call_args.args[0] == "https://api.wenzap.com.br/message/sendMedia/cliente-teste"
    payload = call_args.kwargs["json"]
    assert payload["mediatype"] == "image"
    assert payload["mimetype"] == "image/jpeg"
    assert payload["caption"] == "Toyota Corolla — R$ 88.900,00"
    assert msg.metadata_json["delivery"]["status"] == "sent"


def test_deliver_media_storage_fetch_failure_saves_failure(monkeypatch):
    monkeypatch.setenv("EVOLUTION_TEST_API_KEY", "fake-key")
    channel = _channel()
    contact = _contact()
    db = _FakeDB(channel=channel, contact=contact)
    msg = _message(content_type="audio")
    conv = _conversation(channel_id=channel.id, contact_id=contact.id)

    fake_storage = SimpleNamespace(get_file=lambda key: (_ for _ in ()).throw(RuntimeError("nope")))
    with patch("app.services.storage.factory.get_storage_provider", return_value=fake_storage):
        _PROVIDER.deliver_media(
            db, msg, conv, storage_key="conversation-media/ws/voice.ogg", mime_type="audio/ogg"
        )

    assert msg.metadata_json["delivery"]["error_type"] == "storage_fetch_failed"


def test_deliver_media_channel_not_found_saves_failure():
    db = _FakeDB(channel=None)
    msg = _message(content_type="audio")
    conv = _conversation(channel_id=None)
    _PROVIDER.deliver_media(db, msg, conv, storage_key="x", mime_type="audio/ogg")
    assert msg.metadata_json["delivery"]["error_type"] == "channel_not_found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
