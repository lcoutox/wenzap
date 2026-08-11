"""
Tests for messaging/meta_provider.py — MetaOutboundProvider.deliver_media.

No test coverage existed for this before meta-cloud-api-parity-prd.md
(confirmed: image delivery via Meta was built but completely untested).
Covers the pre-existing image path and the new audio path added by this PRD.
"""

import uuid
from unittest.mock import MagicMock, patch

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.messaging.meta_provider import MetaOutboundProvider
from tests.conftest import _make_user, _make_workspace

_RESOLVE_TOKEN = "app.services.whatsapp_outbound_service._resolve_access_token"
_GET_STORAGE = "app.services.storage.factory.get_storage_provider"
_HTTP_POST = "app.services.messaging.meta_provider.httpx.post"


def _make_agent(db, ws_id):
    agent = Agent(workspace_id=ws_id, name="Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_channel(db, ws_id, agent_id):
    channel = Channel(
        workspace_id=ws_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="WA Channel",
        public_key=str(uuid.uuid4()),
        status="active",
        config_json={
            "provider": "meta_cloud_api",
            "phone_number_id": "PN123",
            "access_token_ref": "db:fake",
        },
    )
    db.add(channel)
    db.flush()
    return channel


def _make_contact(db, ws_id):
    contact = Contact(workspace_id=ws_id, name="Cliente", phone="+5511999999999")
    db.add(contact)
    db.flush()
    return contact


def _make_conversation(db, ws_id, channel, contact):
    conv = Conversation(
        workspace_id=ws_id,
        channel_id=channel.id,
        contact_id=contact.id,
        channel_type="whatsapp",
        status="open",
    )
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


def _make_message(db, ws_id, conv, *, content_type):
    msg = ConversationMessage(
        workspace_id=ws_id,
        conversation_id=conv.id,
        direction="outbound",
        sender_type="agent",
        content="conteúdo",
        content_type=content_type,
    )
    db.add(msg)
    db.flush()
    db.refresh(msg)
    return msg


def _fake_success_response(wamid: str = "wamid.META123") -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"messages": [{"id": wamid}]}
    return resp


def _setup(db, *, content_type: str):
    owner = _make_user(db, f"u{uuid.uuid4().hex[:6]}@t.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    agent = _make_agent(db, ws.id)
    channel = _make_channel(db, ws.id, agent.id)
    contact = _make_contact(db, ws.id)
    conv = _make_conversation(db, ws.id, channel, contact)
    msg = _make_message(db, ws.id, conv, content_type=content_type)
    db.commit()
    return ws, conv, msg


class TestDeliverMediaUnsupportedContentType:
    def test_text_content_type_records_failure(self, db):
        _, conv, msg = _setup(db, content_type="text")
        MetaOutboundProvider().deliver_media(
            db, msg, conv, storage_key="k", mime_type="image/jpeg"
        )
        assert msg.metadata_json["delivery"]["status"] == "failed"
        assert msg.metadata_json["delivery"]["error"] == "unsupported_content_type"


class TestDeliverMediaImage:
    def test_success_sends_image_and_records_sent(self, db):
        _, conv, msg = _setup(db, content_type="image")
        storage = MagicMock()
        storage.generate_presigned_url.return_value = "https://cdn.example.com/img.jpg"

        with (
            patch(_RESOLVE_TOKEN, return_value="meta-token"),
            patch(_GET_STORAGE, return_value=storage),
            patch(_HTTP_POST, return_value=_fake_success_response()) as mock_post,
        ):
            MetaOutboundProvider().deliver_media(
                db, msg, conv, storage_key="k.jpg", mime_type="image/jpeg", caption="Produto X"
            )

        assert msg.metadata_json["delivery"]["status"] == "sent"
        assert msg.external_message_id == "wamid.META123"

        request_body = mock_post.call_args.kwargs["json"]
        assert request_body["type"] == "image"
        assert request_body["image"] == {
            "link": "https://cdn.example.com/img.jpg",
            "caption": "Produto X",
        }
        assert request_body["to"] == "5511999999999"

    def test_missing_token_records_failure_without_http_call(self, db):
        _, conv, msg = _setup(db, content_type="image")
        with (
            patch(_RESOLVE_TOKEN, return_value=None),
            patch(_HTTP_POST) as mock_post,
        ):
            MetaOutboundProvider().deliver_media(
                db, msg, conv, storage_key="k.jpg", mime_type="image/jpeg"
            )

        assert msg.metadata_json["delivery"]["status"] == "failed"
        mock_post.assert_not_called()

    def test_presigned_url_failure_records_failure(self, db):
        _, conv, msg = _setup(db, content_type="image")
        storage = MagicMock()
        storage.generate_presigned_url.side_effect = Exception("bucket unreachable")

        with (
            patch(_RESOLVE_TOKEN, return_value="meta-token"),
            patch(_GET_STORAGE, return_value=storage),
        ):
            MetaOutboundProvider().deliver_media(
                db, msg, conv, storage_key="k.jpg", mime_type="image/jpeg"
            )

        assert msg.metadata_json["delivery"]["status"] == "failed"
        assert "bucket unreachable" in msg.metadata_json["delivery"]["error"]

    def test_meta_api_error_records_failure(self, db):
        _, conv, msg = _setup(db, content_type="image")
        storage = MagicMock()
        storage.generate_presigned_url.return_value = "https://cdn.example.com/img.jpg"

        with (
            patch(_RESOLVE_TOKEN, return_value="meta-token"),
            patch(_GET_STORAGE, return_value=storage),
            patch(_HTTP_POST, side_effect=Exception("401 invalid token")),
        ):
            MetaOutboundProvider().deliver_media(
                db, msg, conv, storage_key="k.jpg", mime_type="image/jpeg"
            )

        assert msg.metadata_json["delivery"]["status"] == "failed"


class TestDeliverMediaAudio:
    def test_success_sends_audio_and_records_sent(self, db):
        _, conv, msg = _setup(db, content_type="audio")
        storage = MagicMock()
        storage.generate_presigned_url.return_value = "https://cdn.example.com/voice.mp3"

        with (
            patch(_RESOLVE_TOKEN, return_value="meta-token"),
            patch(_GET_STORAGE, return_value=storage),
            patch(_HTTP_POST, return_value=_fake_success_response("wamid.AUDIO1")) as mock_post,
        ):
            MetaOutboundProvider().deliver_media(
                db, msg, conv, storage_key="k.mp3", mime_type="audio/mpeg"
            )

        assert msg.metadata_json["delivery"]["status"] == "sent"
        assert msg.external_message_id == "wamid.AUDIO1"

        request_body = mock_post.call_args.kwargs["json"]
        assert request_body["type"] == "audio"
        # Audio has no caption concept in the Meta API — must never be sent.
        assert request_body["audio"] == {"link": "https://cdn.example.com/voice.mp3"}

    def test_caption_is_ignored_for_audio(self, db):
        _, conv, msg = _setup(db, content_type="audio")
        storage = MagicMock()
        storage.generate_presigned_url.return_value = "https://cdn.example.com/voice.mp3"

        with (
            patch(_RESOLVE_TOKEN, return_value="meta-token"),
            patch(_GET_STORAGE, return_value=storage),
            patch(_HTTP_POST, return_value=_fake_success_response()) as mock_post,
        ):
            MetaOutboundProvider().deliver_media(
                db,
                msg,
                conv,
                storage_key="k.mp3",
                mime_type="audio/mpeg",
                caption="isso deve ser ignorado",
            )

        assert "caption" not in mock_post.call_args.kwargs["json"]["audio"]

    def test_meta_api_error_records_failure(self, db):
        _, conv, msg = _setup(db, content_type="audio")
        storage = MagicMock()
        storage.generate_presigned_url.return_value = "https://cdn.example.com/voice.mp3"

        with (
            patch(_RESOLVE_TOKEN, return_value="meta-token"),
            patch(_GET_STORAGE, return_value=storage),
            patch(_HTTP_POST, side_effect=Exception("unsupported media type")),
        ):
            MetaOutboundProvider().deliver_media(
                db, msg, conv, storage_key="k.mp3", mime_type="audio/mpeg"
            )

        assert msg.metadata_json["delivery"]["status"] == "failed"
