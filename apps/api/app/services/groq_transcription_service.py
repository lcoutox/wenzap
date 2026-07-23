"""
Groq audio transcription — whatsapp-voice-groq-elevenlabs-prd.md.

Transcribes an inbound WhatsApp voice note so its text can be used as the
customer's message content, same principle as Chatvolt's
docs.chatvolt.ai/agent/transcriptions-with-groq. Uses Groq's OpenAI-compatible
Whisper endpoint.

Never raises — a transcription failure must not break message persistence;
the caller falls back to a placeholder content string.

⚠️ Not yet smoke-tested against the real Groq API (only built from Groq's
public docs) — same caveat as the rest of this session's media pipeline.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
_TIMEOUT = 30.0  # audio uploads/transcription take longer than a text call
_MODEL = "whisper-large-v3-turbo"


def transcribe_audio(
    api_key: str,
    audio_bytes: bytes,
    *,
    filename: str = "audio.ogg",
    content_type: str = "audio/ogg",
) -> str | None:
    """
    Transcribe *audio_bytes* via Groq. Returns the transcript text, or None
    on any failure (missing/invalid key, network error, empty transcript).
    """
    if not api_key:
        logger.warning("groq_transcription missing api_key")
        return None

    try:
        response = httpx.post(
            _TRANSCRIPTION_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": _MODEL, "response_format": "text"},
            files={"file": (filename, audio_bytes, content_type)},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "groq_transcription http_error status=%s body=%s",
            exc.response.status_code,
            exc.response.text[:300],
        )
        return None
    except httpx.RequestError:
        logger.exception("groq_transcription request_error")
        return None

    # response_format=text returns the raw transcript as the response body,
    # not JSON — strip incidental whitespace/newlines from the API.
    text = response.text.strip()
    if not text:
        logger.warning("groq_transcription empty transcript")
        return None
    return text
