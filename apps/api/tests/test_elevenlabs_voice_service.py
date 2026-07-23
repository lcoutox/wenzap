"""
Tests for elevenlabs_voice_service.synthesize_speech —
whatsapp-voice-groq-elevenlabs-prd.md.

Never raises: every failure mode returns None so a synthesis failure never
breaks the (already-sent) text reply.
"""

from unittest.mock import patch

import httpx

from app.services.elevenlabs_voice_service import synthesize_speech

_HTTP_POST = "httpx.post"


def _response(status_code: int = 200, content: bytes = b"\x00\x01mp3-bytes") -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=content,
        request=httpx.Request("POST", "https://api.elevenlabs.io/v1/text-to-speech/voice123"),
    )


def test_synthesize_success_returns_audio_bytes():
    with patch(_HTTP_POST, return_value=_response()) as mock_post:
        result = synthesize_speech("api-key", "Olá, tudo bem?", "voice123")

    assert result == b"\x00\x01mp3-bytes"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["xi-api-key"] == "api-key"
    assert kwargs["json"]["text"] == "Olá, tudo bem?"


def test_synthesize_missing_api_key_returns_none():
    assert synthesize_speech("", "text", "voice123") is None


def test_synthesize_missing_voice_id_returns_none():
    assert synthesize_speech("api-key", "text", "") is None


def test_synthesize_empty_text_returns_none():
    assert synthesize_speech("api-key", "   ", "voice123") is None


def test_synthesize_http_error_returns_none():
    with patch(_HTTP_POST, return_value=_response(status_code=401, content=b"unauthorized")):
        assert synthesize_speech("bad-key", "text", "voice123") is None


def test_synthesize_request_error_returns_none():
    with patch(_HTTP_POST, side_effect=httpx.ConnectError("conn refused")):
        assert synthesize_speech("api-key", "text", "voice123") is None


def test_synthesize_empty_audio_response_returns_none():
    with patch(_HTTP_POST, return_value=_response(content=b"")):
        assert synthesize_speech("api-key", "text", "voice123") is None
