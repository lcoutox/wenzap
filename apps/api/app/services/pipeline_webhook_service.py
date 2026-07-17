"""
Pipeline stage webhook dispatch — Pipeline.2 Fase 1.

Fires a POST to PipelineStage.webhook_url whenever an entry enters that stage
(manual move, entry_condition auto-route, or stay_limit auto-advance).

Fire-and-forget via a daemon thread (same pattern as auto_reply_scheduler.py)
so a slow/unreachable third-party endpoint never holds up the HTTP response
that triggered the move.
"""

import ipaddress
import logging
import socket
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_WEBHOOK_TIMEOUT_SECONDS = 8.0


class WebhookUrlError(ValueError):
    """Raised when a stage webhook_url is invalid or points to a private/internal address."""


def validate_webhook_url(url: str) -> None:
    """
    Raise WebhookUrlError if *url* is not a safe, public HTTP(S) destination.

    Called both when a stage is saved (immediate feedback to the user) and
    defensively right before every dispatch (DNS can change between save and
    fire — DNS rebinding protection).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise WebhookUrlError("A URL do webhook deve usar http:// ou https://.")
    if not parsed.hostname:
        raise WebhookUrlError("A URL do webhook deve incluir um hostname.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise WebhookUrlError(f"Não foi possível resolver o hostname do webhook: {exc}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise WebhookUrlError(
                "A URL do webhook resolve para um endereço privado/interno, o que não é permitido."
            )


def dispatch_stage_entered_webhook(
    *,
    webhook_url: str,
    webhook_auth_header: str | None,
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
    stage_name: str,
    entry_id: uuid.UUID,
    conversation_id: uuid.UUID,
    contact_id: uuid.UUID | None,
    contact_name: str | None,
    contact_phone: str | None,
    previous_stage_id: uuid.UUID | None,
) -> None:
    """Fire the STAGE_ENTERED webhook in a background thread. Never raises."""
    payload = {
        "event": "STAGE_ENTERED",
        "pipeline_id": str(pipeline_id),
        "stage_id": str(stage_id),
        "stage_name": stage_name,
        "entry_id": str(entry_id),
        "conversation_id": str(conversation_id),
        "contact_id": str(contact_id) if contact_id else None,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "previous_stage_id": str(previous_stage_id) if previous_stage_id else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    t = threading.Thread(
        target=_send,
        args=(webhook_url, webhook_auth_header, payload),
        daemon=True,
        name=f"pipeline-webhook-{entry_id}",
    )
    t.start()


def _send(webhook_url: str, webhook_auth_header: str | None, payload: dict) -> None:
    headers = {"Content-Type": "application/json"}
    if webhook_auth_header:
        headers["Authorization"] = webhook_auth_header

    for attempt in range(2):  # 1 retry
        try:
            validate_webhook_url(webhook_url)  # re-check right before send (DNS rebinding)
            response = httpx.post(
                webhook_url, json=payload, headers=headers, timeout=_WEBHOOK_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            logger.info(
                "pipeline_webhook delivered entry_id=%s status=%s",
                payload["entry_id"], response.status_code,
            )
            return
        except WebhookUrlError as exc:
            logger.warning(
                "pipeline_webhook rejected entry_id=%s reason=%s",
                payload["entry_id"], exc,
            )
            return  # do not retry — the URL is unsafe, not transiently failing
        except httpx.TimeoutException:
            logger.warning(
                "pipeline_webhook timeout entry_id=%s attempt=%d", payload["entry_id"], attempt
            )
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "pipeline_webhook http_error entry_id=%s status=%s attempt=%d",
                payload["entry_id"], exc.response.status_code, attempt,
            )
        except httpx.RequestError as exc:
            logger.warning(
                "pipeline_webhook request_error entry_id=%s error=%s attempt=%d",
                payload["entry_id"], type(exc).__name__, attempt,
            )

    logger.error("pipeline_webhook failed after retry entry_id=%s", payload["entry_id"])
