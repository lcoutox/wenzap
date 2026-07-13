"""Evolution API instance provisioning — bridge WhatsApp provider (Slice 4).

Orchestrates: create Evolution instance (QR code) → create Channel + encrypted
ChannelCredential → configure the instance's webhook → (later) poll connection
state → (later) disconnect.

Two distinct credentials are involved (confirmed empirically against a live
Evolution v2.3.7 server on 2026-07-13 — see negocios/wenzap/plano-evolution-api.md):

  - settings.evolution_master_api_key — the Evolution server's own admin key
    (AUTHENTICATION_API_KEY). Used ONLY here, server-side, to create/delete
    instances. Never stored per-channel, never exposed to the frontend.
  - The instance's own token (Evolution's `hash` field, returned once at
    creation) — stored per-channel via ChannelCredential/api_key_ref, and used
    for that instance's own send/receive/webhook operations (EvolutionOutboundProvider,
    evolution_webhooks router — built in Slices 2-3, unchanged here).

Design notes:
- Instance creation/deletion call the Evolution management API directly and
  MAY raise HTTPException — unlike the webhook receivers (Slices 2-3), this is
  a synchronous, user-facing action (the user is waiting for a QR code), so
  failures should surface, not be silently swallowed.
- Webhook registration is best-effort: a failure is logged but does not fail
  channel creation (the QR/channel are still useful; the webhook can be
  reconfigured later without redoing the whole flow).
"""

import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.channel import Channel
from app.schemas.channel import ChannelOut
from app.services.channel_credentials_service import (
    create_or_update_channel_credential,
    resolve_channel_secret,
)
from app.services.channel_service import _channel_to_out, _generate_public_key

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0
PROVIDER_KEY = "evolution_api"


class EvolutionProvisioningError(Exception):
    """Raised when the Evolution management API call fails unexpectedly."""


# ── Public API ────────────────────────────────────────────────────────────────


def provision_evolution_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> tuple[ChannelOut, str | None, str | None]:
    """
    Create a new Evolution instance and its Channel/ChannelCredential.

    Returns (channel, qrcode_base64, pairing_code). qrcode_base64 is a
    data:image/png;base64,... string ready to render directly in an <img> tag.

    Raises HTTPException (502/500) if instance creation fails — the caller is
    waiting synchronously for a QR code, so failures must surface immediately.
    """
    _require_master_config()

    instance_name = f"wenzap-{uuid.uuid4().hex[:12]}"
    create_resp = _call_create_instance(instance_name)

    token = create_resp.get("hash")
    qrcode = create_resp.get("qrcode") or {}
    qrcode_base64 = qrcode.get("base64")
    pairing_code = qrcode.get("pairingCode")

    if not token:
        raise EvolutionProvisioningError(
            f"Evolution create response missing 'hash' token for instance={instance_name}"
        )

    now = datetime.now(timezone.utc)
    config = {
        "provider": PROVIDER_KEY,
        "onboarding_type": "qr_code",
        "base_url": settings.evolution_api_base_url,
        "instance_name": instance_name,
        "display_phone_number": None,
        "api_key_ref": None,  # set below, after the credential is created
        "status": "testing",
        "connected_at": None,
        "last_webhook_at": None,
        "auto_reply_enabled": False,
    }

    channel = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name=f"WhatsApp (Evolution) {instance_name}",
        public_key=_generate_public_key("whatsapp"),
        status="active",
        config_json=config,
    )
    db.add(channel)
    db.flush()  # populate channel.id before creating the credential

    cred = create_or_update_channel_credential(
        db,
        workspace_id=workspace_id,
        channel_id=channel.id,
        provider=PROVIDER_KEY,
        credential_type="evolution_instance_token",
        plain_value=token,
        obtained_via="qr_code",
        metadata_json={"instance_name": instance_name},
    )
    channel.config_json = {**channel.config_json, "api_key_ref": f"db:{cred.id}"}
    channel.updated_at = now
    db.commit()
    db.refresh(channel)

    logger.info(
        "evolution_provisioning channel created channel_id=%s instance=%s workspace=%s",
        channel.id,
        instance_name,
        workspace_id,
    )

    _configure_webhook_best_effort(instance_name, token)

    return _channel_to_out(channel), qrcode_base64, pairing_code


def check_evolution_connection_status(db: Session, channel: Channel) -> str:
    """
    Poll the Evolution instance's connection state and sync channel.status.

    Returns the raw Evolution state ("open", "connecting", "close", ...).
    On first observed "open", marks the channel active + sets connected_at.
    """
    config = channel.config_json or {}
    base_url = config.get("base_url")
    instance_name = config.get("instance_name")
    token = resolve_channel_secret(db, channel, config.get("api_key_ref"))

    if not base_url or not instance_name or not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evolution channel is missing base_url, instance_name or credential.",
        )

    state = _call_connection_state(base_url, instance_name, token)

    if state == "open" and config.get("status") != "active":
        now = datetime.now(timezone.utc)
        channel.config_json = {
            **config,
            "status": "active",
            "connected_at": now.isoformat(),
        }
        channel.updated_at = now
        db.commit()
        logger.info(
            "evolution_provisioning channel connected channel_id=%s instance=%s",
            channel.id,
            instance_name,
        )

    return state


def disconnect_evolution_channel(db: Session, channel: Channel) -> None:
    """
    Archive the channel and best-effort delete the Evolution instance.

    Mirrors the resilience contract of outbound delivery: the Evolution-side
    cleanup is best-effort (logged, never raised) so the channel is always
    archived even if the instance is already gone or the server is unreachable.
    """
    instance_name = (channel.config_json or {}).get("instance_name")

    channel.status = "archived"
    channel.updated_at = datetime.now(timezone.utc)
    db.commit()

    if not instance_name:
        return

    try:
        _call_delete_instance(instance_name)
        logger.info("evolution_provisioning instance deleted instance=%s", instance_name)
    except Exception:
        logger.exception(
            "evolution_provisioning instance delete failed instance=%s — channel archived anyway",
            instance_name,
        )


# ── Evolution management API calls ──────────────────────────────────────────


def _require_master_config() -> None:
    if not settings.evolution_api_base_url or not settings.evolution_master_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evolution API is not configured on this server.",
        )


def _call_create_instance(instance_name: str) -> dict:
    url = f"{settings.evolution_api_base_url.rstrip('/')}/instance/create"
    try:
        response = httpx.post(
            url,
            json={
                "instanceName": instance_name,
                "integration": "WHATSAPP-BAILEYS",
                "qrcode": True,
            },
            headers={
                "apikey": settings.evolution_master_api_key,
                "Content-Type": "application/json",
            },
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        logger.exception("evolution_provisioning create_instance failed instance=%s", instance_name)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create the Evolution instance.",
        ) from exc


def _call_delete_instance(instance_name: str) -> None:
    url = f"{settings.evolution_api_base_url.rstrip('/')}/instance/delete/{instance_name}"
    response = httpx.delete(
        url,
        headers={"apikey": settings.evolution_master_api_key},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()


def _call_connection_state(base_url: str, instance_name: str, token: str) -> str:
    url = f"{base_url.rstrip('/')}/instance/connectionState/{instance_name}"
    try:
        response = httpx.get(url, headers={"apikey": token}, timeout=_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return (data.get("instance") or {}).get("state", "unknown")
    except httpx.HTTPError as exc:
        logger.exception(
            "evolution_provisioning connection_state failed instance=%s", instance_name
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to check the Evolution instance connection state.",
        ) from exc


def _configure_webhook_best_effort(instance_name: str, token: str) -> None:
    if not settings.api_public_base_url:
        logger.warning(
            "evolution_provisioning skipping webhook setup — API_PUBLIC_BASE_URL not configured "
            "instance=%s",
            instance_name,
        )
        return

    webhook_url = (
        f"{settings.api_public_base_url.rstrip('/')}/webhooks/whatsapp/evolution/{instance_name}"
    )
    url = f"{settings.evolution_api_base_url.rstrip('/')}/webhook/set/{instance_name}"
    try:
        response = httpx.post(
            url,
            json={"webhook": {"url": webhook_url, "enabled": True, "events": ["MESSAGES_UPSERT"]}},
            headers={"apikey": token, "Content-Type": "application/json"},
            timeout=_TIMEOUT,
        )
        response.raise_for_status()
        logger.info(
            "evolution_provisioning webhook configured instance=%s url=%s",
            instance_name,
            webhook_url,
        )
    except httpx.HTTPError:
        logger.exception(
            "evolution_provisioning webhook setup failed instance=%s — channel usable, "
            "webhook must be configured manually or retried",
            instance_name,
        )
