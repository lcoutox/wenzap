"""
Email delivery abstraction.

In dev/test: FakeEmailService logs and captures sent emails (no external calls).
In production: ResendEmailService sends via Resend HTTP API using httpx.

Usage:
    from app.services.email_service import get_email_service
    svc = get_email_service()
    svc.send(to=..., subject=..., html=..., text=...)

Provider selection:
  - email_sandbox_mode=True (env: EMAIL_SANDBOX_MODE=true) → FakeEmailService
  - Otherwise → ResendEmailService (requires RESEND_API_KEY and EMAIL_FROM)
"""

import logging
from typing import Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService(Protocol):
    def send(self, *, to: str, subject: str, html: str, text: str) -> None: ...


# ── Fake (dev / test) ─────────────────────────────────────────────────────────

class FakeEmailService:
    """Captures sent emails in memory; never makes external calls."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        self.sent.append({"to": to, "subject": subject, "html": html, "text": text})
        logger.info("[FakeEmail] To=%s Subject=%s", to, subject)


# ── Resend (production) ───────────────────────────────────────────────────────

class ResendEmailService:
    """Sends transactional email via Resend API using httpx."""

    _RESEND_API_URL = "https://api.resend.com/emails"

    def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        api_key = settings.resend_api_key
        email_from = settings.email_from
        if not api_key or not email_from:
            raise RuntimeError(
                "Email delivery is not configured. "
                "Set RESEND_API_KEY and EMAIL_FROM in your environment."
            )

        payload = {
            "from": f"{settings.email_from_name} <{email_from}>",
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                self._RESEND_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code not in (200, 201):
            logger.error(
                "Resend error: status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            raise RuntimeError(f"Failed to send email via Resend (status {response.status_code})")

        logger.info("Email sent via Resend: to=%s subject=%s", to, subject)


# ── Factory ───────────────────────────────────────────────────────────────────

# Module-level singleton — replaced in tests via dependency injection or monkeypatch
_instance: EmailService | None = None


def get_email_service() -> EmailService:
    global _instance  # noqa: PLW0603
    if _instance is None:
        if settings.email_sandbox_mode or not settings.resend_api_key:
            _instance = FakeEmailService()
        else:
            _instance = ResendEmailService()
    return _instance


def override_email_service(svc: EmailService) -> None:
    """Replace the singleton — intended for tests only."""
    global _instance  # noqa: PLW0603
    _instance = svc


def reset_email_service() -> None:
    """Reset singleton so next call re-reads settings — for tests."""
    global _instance  # noqa: PLW0603
    _instance = None
