"""
Email delivery abstraction.

In dev/test: FakeEmailService logs and captures sent emails (no external calls).
In production: SendGridEmailService sends via SendGrid HTTP API using httpx.

Usage:
    from app.services.email_service import get_email_service
    svc = get_email_service()
    svc.send(to=..., subject=..., html=..., text=...)

Provider selection:
  - email_sandbox_mode=True (env: EMAIL_SANDBOX_MODE=true) → FakeEmailService
  - Otherwise → SendGridEmailService (requires SENDGRID_API_KEY and EMAIL_FROM)
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


# ── SendGrid (production) ─────────────────────────────────────────────────────

class SendGridEmailService:
    """Sends transactional email via SendGrid v3 API using httpx."""

    _SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"

    def send(self, *, to: str, subject: str, html: str, text: str) -> None:
        api_key = settings.sendgrid_api_key
        email_from = settings.email_from
        if not api_key or not email_from:
            raise RuntimeError(
                "Email delivery is not configured. "
                "Set SENDGRID_API_KEY and EMAIL_FROM in your environment."
            )

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": email_from, "name": settings.email_from_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text},
                {"type": "text/html", "value": html},
            ],
        }

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                self._SENDGRID_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code not in (200, 202):
            logger.error(
                "SendGrid error: status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
            raise RuntimeError(f"Failed to send email via SendGrid (status {response.status_code})")

        logger.info("Email sent via SendGrid: to=%s subject=%s", to, subject)


# ── Factory ───────────────────────────────────────────────────────────────────

# Module-level singleton — replaced in tests via dependency injection or monkeypatch
_instance: EmailService | None = None


def get_email_service() -> EmailService:
    global _instance  # noqa: PLW0603
    if _instance is None:
        if settings.email_sandbox_mode or not settings.sendgrid_api_key:
            _instance = FakeEmailService()
        else:
            _instance = SendGridEmailService()
    return _instance


def override_email_service(svc: EmailService) -> None:
    """Replace the singleton — intended for tests only."""
    global _instance  # noqa: PLW0603
    _instance = svc


def reset_email_service() -> None:
    """Reset singleton so next call re-reads settings — for tests."""
    global _instance  # noqa: PLW0603
    _instance = None
