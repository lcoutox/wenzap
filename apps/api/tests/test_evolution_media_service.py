"""
Tests for evolution_media_service.py — conversation-image-upload-prd.md.

Coverage:
- success: downloads base64, decodes, uploads via storage, returns (key, mime_type)
- missing base_url/instance_name → None
- missing/unresolvable api key → None
- httpx request failure → None
- response missing base64 → None
- invalid base64 → None
- storage.put_file failure → None
- default mime_type used when response omits mimetype
"""

import base64
import uuid
from unittest.mock import MagicMock, patch

from app.models.channel import Channel
from app.services.evolution_media_service import download_and_store_inbound_image


def _make_channel(
    workspace_id: uuid.UUID | None = None,
    base_url: str | None = "https://evolution.example.com",
    instance_name: str | None = "wenzap",
    api_key_ref: str | None = "env:EVOLUTION_TEST_KEY",
) -> Channel:
    # In-memory only (no db.add/flush) — the function under test only reads
    # attributes off this object, never persists it. Uses the normal
    # constructor (not __new__), which is broken for ORM objects here (see
    # follow-up-tool-prd.md's "Achado colateral" — __new__ never initializes
    # _sa_instance_state).
    return Channel(
        id=uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        config_json={
            "provider": "evolution_api",
            "base_url": base_url,
            "instance_name": instance_name,
            "api_key_ref": api_key_ref,
        },
    )


def _fake_httpx_response(json_body: dict, status_ok: bool = True) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_body
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = Exception("http error")
    return resp


class TestDownloadAndStoreInboundImage:
    def test_success_decodes_and_uploads(self, db):
        channel = _make_channel()
        image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        storage = MagicMock()

        with (
            patch(
                "app.services.evolution_media_service.resolve_channel_secret",
                return_value="test-api-key",
            ),
            patch(
                "app.services.evolution_media_service.httpx.post",
                return_value=_fake_httpx_response({"base64": encoded, "mimetype": "image/jpeg"}),
            ) as mock_post,
        ):
            result = download_and_store_inbound_image(
                db, channel, storage, wamid="WAMID1", from_wa_id="5537999999999"
            )

        assert result is not None
        key, mime_type = result
        assert mime_type == "image/jpeg"
        assert key.startswith(f"conversation-media/{channel.workspace_id}/")
        assert key.endswith(".jpeg")

        storage.put_file.assert_called_once()
        call_args = storage.put_file.call_args
        assert call_args.args[0] == key
        assert call_args.args[1] == image_bytes
        assert call_args.kwargs["content_type"] == "image/jpeg"

        # Confirms the request targets Evolution's own media-decrypt endpoint.
        request_url = mock_post.call_args.args[0]
        assert request_url == "https://evolution.example.com/chat/getBase64FromMediaMessage/wenzap"
        request_body = mock_post.call_args.kwargs["json"]
        assert request_body["message"]["key"]["id"] == "WAMID1"
        assert request_body["message"]["key"]["remoteJid"] == "5537999999999@s.whatsapp.net"

    def test_default_mime_type_when_missing(self, db):
        channel = _make_channel()
        storage = MagicMock()
        encoded = base64.b64encode(b"bytes").decode("ascii")

        with (
            patch(
                "app.services.evolution_media_service.resolve_channel_secret",
                return_value="test-api-key",
            ),
            patch(
                "app.services.evolution_media_service.httpx.post",
                return_value=_fake_httpx_response({"base64": encoded}),
            ),
        ):
            result = download_and_store_inbound_image(
                db, channel, storage, wamid="WAMID2", from_wa_id="5537999999999"
            )

        assert result is not None
        _key, mime_type = result
        assert mime_type == "image/jpeg"

    def test_missing_base_url_returns_none(self, db):
        channel = _make_channel(base_url=None)
        storage = MagicMock()

        result = download_and_store_inbound_image(
            db, channel, storage, wamid="WAMID3", from_wa_id="5537999999999"
        )

        assert result is None
        storage.put_file.assert_not_called()

    def test_missing_instance_name_returns_none(self, db):
        channel = _make_channel(instance_name=None)
        storage = MagicMock()

        result = download_and_store_inbound_image(
            db, channel, storage, wamid="WAMID4", from_wa_id="5537999999999"
        )

        assert result is None

    def test_unresolvable_api_key_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with patch(
            "app.services.evolution_media_service.resolve_channel_secret",
            return_value=None,
        ):
            result = download_and_store_inbound_image(
                db, channel, storage, wamid="WAMID5", from_wa_id="5537999999999"
            )

        assert result is None
        storage.put_file.assert_not_called()

    def test_http_request_failure_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.evolution_media_service.resolve_channel_secret",
                return_value="test-api-key",
            ),
            patch(
                "app.services.evolution_media_service.httpx.post",
                side_effect=Exception("network error"),
            ),
        ):
            result = download_and_store_inbound_image(
                db, channel, storage, wamid="WAMID6", from_wa_id="5537999999999"
            )

        assert result is None

    def test_response_missing_base64_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.evolution_media_service.resolve_channel_secret",
                return_value="test-api-key",
            ),
            patch(
                "app.services.evolution_media_service.httpx.post",
                return_value=_fake_httpx_response({"mimetype": "image/jpeg"}),
            ),
        ):
            result = download_and_store_inbound_image(
                db, channel, storage, wamid="WAMID7", from_wa_id="5537999999999"
            )

        assert result is None
        storage.put_file.assert_not_called()

    def test_invalid_base64_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.evolution_media_service.resolve_channel_secret",
                return_value="test-api-key",
            ),
            patch(
                "app.services.evolution_media_service.httpx.post",
                return_value=_fake_httpx_response(
                    {"base64": "not-valid-base64!!!", "mimetype": "image/jpeg"}
                ),
            ),
        ):
            result = download_and_store_inbound_image(
                db, channel, storage, wamid="WAMID8", from_wa_id="5537999999999"
            )

        assert result is None
        storage.put_file.assert_not_called()

    def test_storage_upload_failure_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()
        storage.put_file.side_effect = Exception("disk full")
        encoded = base64.b64encode(b"bytes").decode("ascii")

        with (
            patch(
                "app.services.evolution_media_service.resolve_channel_secret",
                return_value="test-api-key",
            ),
            patch(
                "app.services.evolution_media_service.httpx.post",
                return_value=_fake_httpx_response({"base64": encoded, "mimetype": "image/png"}),
            ),
        ):
            result = download_and_store_inbound_image(
                db, channel, storage, wamid="WAMID9", from_wa_id="5537999999999"
            )

        assert result is None
