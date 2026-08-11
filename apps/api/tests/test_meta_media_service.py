"""
Tests for meta_media_service.py — meta-cloud-api-parity-prd.md.

Coverage:
- success: fetches media url, downloads bytes, uploads via storage, returns (key, mime_type)
- missing access_token_ref → None
- unresolvable token → None
- url-fetch request failure → None
- response missing url → None
- bytes-download request failure → None
- storage.put_file failure → None
- mime_type falls back to hint, then to media_kind default, when response omits it
"""

import uuid
from unittest.mock import MagicMock, patch

from app.models.channel import Channel
from app.services.meta_media_service import download_and_store_inbound_media


def _make_channel(
    workspace_id: uuid.UUID | None = None,
    access_token_ref: str | None = "env:META_TEST_TOKEN",
) -> Channel:
    return Channel(
        id=uuid.uuid4(),
        workspace_id=workspace_id or uuid.uuid4(),
        config_json={
            "provider": "meta_cloud_api",
            "access_token_ref": access_token_ref,
        },
    )


def _fake_response(json_body: dict | None = None, content: bytes | None = None) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    if json_body is not None:
        resp.json.return_value = json_body
    if content is not None:
        resp.content = content
    return resp


class TestDownloadAndStoreInboundMedia:
    def test_success_downloads_and_uploads_image(self, db):
        channel = _make_channel()
        storage = MagicMock()
        image_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"

        with (
            patch(
                "app.services.meta_media_service.resolve_channel_secret",
                return_value="test-token",
            ),
            patch(
                "app.services.meta_media_service.httpx.get",
                side_effect=[
                    _fake_response(
                        {"url": "https://cdn.meta.example/x", "mime_type": "image/jpeg"}
                    ),
                    _fake_response(content=image_bytes),
                ],
            ) as mock_get,
        ):
            result = download_and_store_inbound_media(
                db, channel, storage, media_id="MEDIA_ID_1", media_kind="image"
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

        first_call, second_call = mock_get.call_args_list
        assert first_call.args[0] == "https://graph.facebook.com/v21.0/MEDIA_ID_1"
        assert first_call.kwargs["headers"]["Authorization"] == "Bearer test-token"
        assert second_call.args[0] == "https://cdn.meta.example/x"
        assert second_call.kwargs["headers"]["Authorization"] == "Bearer test-token"

    def test_mime_type_falls_back_to_hint_then_media_kind_default(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.meta_media_service.resolve_channel_secret",
                return_value="test-token",
            ),
            patch(
                "app.services.meta_media_service.httpx.get",
                side_effect=[
                    _fake_response({"url": "https://cdn.meta.example/x"}),
                    _fake_response(content=b"bytes"),
                ],
            ),
        ):
            result = download_and_store_inbound_media(
                db,
                channel,
                storage,
                media_id="MEDIA_ID_2",
                mime_type_hint="audio/ogg; codecs=opus",
                media_kind="audio",
            )

        assert result is not None
        _key, mime_type = result
        assert mime_type == "audio/ogg; codecs=opus"

    def test_mime_type_defaults_by_media_kind_when_no_hint(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.meta_media_service.resolve_channel_secret",
                return_value="test-token",
            ),
            patch(
                "app.services.meta_media_service.httpx.get",
                side_effect=[
                    _fake_response({"url": "https://cdn.meta.example/x"}),
                    _fake_response(content=b"bytes"),
                ],
            ),
        ):
            result = download_and_store_inbound_media(
                db, channel, storage, media_id="MEDIA_ID_3", media_kind="audio"
            )

        assert result is not None
        _key, mime_type = result
        assert mime_type == "audio/ogg"

    def test_missing_access_token_ref_returns_none(self, db):
        channel = _make_channel(access_token_ref=None)
        storage = MagicMock()

        result = download_and_store_inbound_media(db, channel, storage, media_id="MEDIA_ID_4")

        assert result is None
        storage.put_file.assert_not_called()

    def test_unresolvable_token_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with patch(
            "app.services.meta_media_service.resolve_channel_secret", return_value=None
        ):
            result = download_and_store_inbound_media(db, channel, storage, media_id="MEDIA_ID_5")

        assert result is None
        storage.put_file.assert_not_called()

    def test_url_fetch_request_failure_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.meta_media_service.resolve_channel_secret",
                return_value="test-token",
            ),
            patch(
                "app.services.meta_media_service.httpx.get",
                side_effect=Exception("network error"),
            ),
        ):
            result = download_and_store_inbound_media(db, channel, storage, media_id="MEDIA_ID_6")

        assert result is None

    def test_response_missing_url_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.meta_media_service.resolve_channel_secret",
                return_value="test-token",
            ),
            patch(
                "app.services.meta_media_service.httpx.get",
                return_value=_fake_response({"mime_type": "image/jpeg"}),
            ),
        ):
            result = download_and_store_inbound_media(db, channel, storage, media_id="MEDIA_ID_7")

        assert result is None
        storage.put_file.assert_not_called()

    def test_bytes_download_failure_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()

        with (
            patch(
                "app.services.meta_media_service.resolve_channel_secret",
                return_value="test-token",
            ),
            patch(
                "app.services.meta_media_service.httpx.get",
                side_effect=[
                    _fake_response({"url": "https://cdn.meta.example/x"}),
                    Exception("timeout"),
                ],
            ),
        ):
            result = download_and_store_inbound_media(db, channel, storage, media_id="MEDIA_ID_8")

        assert result is None
        storage.put_file.assert_not_called()

    def test_storage_upload_failure_returns_none(self, db):
        channel = _make_channel()
        storage = MagicMock()
        storage.put_file.side_effect = Exception("disk full")

        with (
            patch(
                "app.services.meta_media_service.resolve_channel_secret",
                return_value="test-token",
            ),
            patch(
                "app.services.meta_media_service.httpx.get",
                side_effect=[
                    _fake_response({"url": "https://cdn.meta.example/x", "mime_type": "image/png"}),
                    _fake_response(content=b"bytes"),
                ],
            ),
        ):
            result = download_and_store_inbound_media(db, channel, storage, media_id="MEDIA_ID_9")

        assert result is None
