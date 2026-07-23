"""
Tests for groq_transcription_service.transcribe_audio —
whatsapp-voice-groq-elevenlabs-prd.md.

Never raises: every failure mode returns None so a transcription failure
never breaks inbound message persistence (caller falls back to a
placeholder content string).
"""

from unittest.mock import patch

import httpx

from app.services.groq_transcription_service import transcribe_audio

_HTTP_POST = "httpx.post"


def _response(status_code: int = 200, text: str = "Boa noite, tudo bem?") -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("POST", "https://api.groq.com/openai/v1/audio/transcriptions"),
    )


def test_transcribe_success_returns_text():
    with patch(_HTTP_POST, return_value=_response()) as mock_post:
        result = transcribe_audio("gsk-key", b"raw-audio-bytes")

    assert result == "Boa noite, tudo bem?"
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer gsk-key"
    assert kwargs["files"]["file"][0] == "audio.ogg"


def test_transcribe_strips_surrounding_whitespace():
    with patch(_HTTP_POST, return_value=_response(text="  Boa noite  \n")):
        assert transcribe_audio("gsk-key", b"raw-audio-bytes") == "Boa noite"


def test_transcribe_missing_api_key_returns_none():
    assert transcribe_audio("", b"raw-audio-bytes") is None


def test_transcribe_http_error_returns_none():
    with patch(_HTTP_POST, return_value=_response(status_code=400, text="bad request")):
        assert transcribe_audio("gsk-key", b"raw-audio-bytes") is None


def test_transcribe_request_error_returns_none():
    with patch(_HTTP_POST, side_effect=httpx.ConnectError("conn refused")):
        assert transcribe_audio("gsk-key", b"raw-audio-bytes") is None


def test_transcribe_empty_transcript_returns_none():
    with patch(_HTTP_POST, return_value=_response(text="   ")):
        assert transcribe_audio("gsk-key", b"raw-audio-bytes") is None


def test_transcribe_uses_custom_filename_and_content_type():
    with patch(_HTTP_POST, return_value=_response()) as mock_post:
        transcribe_audio(
            "gsk-key", b"raw-audio-bytes", filename="voice.mp3", content_type="audio/mpeg"
        )

    _, kwargs = mock_post.call_args
    assert kwargs["files"]["file"] == ("voice.mp3", b"raw-audio-bytes", "audio/mpeg")
