"""
ElevenLabs text-to-speech — whatsapp-voice-groq-elevenlabs-prd.md.

Synthesizes the agent's text reply into speech, so it can be sent back as a
WhatsApp voice message — same principle as
docs.chatvolt.ai/agent/elevenLabs-audios.

Never raises — a synthesis failure must not break the (already-sent) text
reply; the caller simply skips the voice message on failure.

⚠️ Not yet smoke-tested against the real ElevenLabs API (only built from
their public docs) — same caveat as the rest of this session's media
pipeline.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_DEFAULT_MODEL_ID = "eleven_multilingual_v2"


def synthesize_speech(
    api_key: str,
    text: str,
    voice_id: str,
) -> bytes | None:
    """
    Synthesize *text* as speech using ElevenLabs' voice *voice_id*.

    Returns the raw MP3 bytes, or None on any failure (missing key/voice_id,
    network error, non-2xx response).
    """
    if not api_key or not voice_id:
        logger.warning("elevenlabs_voice missing api_key or voice_id")
        return None
    if not text.strip():
        logger.warning("elevenlabs_voice empty text")
        return None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    try:
        response = httpx.post(
            url,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={"text": text, "model_id": _DEFAULT_MODEL_ID},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "elevenlabs_voice http_error status=%s body=%s",
            exc.response.status_code,
            exc.response.text[:300],
        )
        return None
    except httpx.RequestError:
        logger.exception("elevenlabs_voice request_error")
        return None

    audio_bytes = response.content
    if not audio_bytes:
        logger.warning("elevenlabs_voice empty audio response")
        return None
    return audio_bytes
