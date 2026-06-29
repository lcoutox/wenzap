"""
WhatsApp Embedded Signup Service — ES.2.

Responsibilities:
1. Generate and verify CSRF state tokens (stateless HMAC, 10-min TTL).
2. Exchange Meta authorization code for short-lived token, then long-lived token.
3. Verify WABA ownership and confirm phone_number_id belongs to the WABA.
4. Create or update the WhatsApp Channel and its encrypted ChannelCredential.

Security rules:
- Never log the authorization code, access tokens, or APP_ENCRYPTION_KEY.
- Never persist the plain token; always encrypt via crypto_service.
- Meta APP_SECRET is used server-side only and never returned to clients.
"""

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.agent import Agent
from app.models.channel import Channel
from app.schemas.channel import ChannelOut
from app.services.channel_credentials_service import (
    create_or_update_channel_credential,
)
from app.services.channel_service import _channel_to_out, _generate_public_key

logger = logging.getLogger(__name__)

_STATE_TTL_SECONDS = 600  # 10 minutes
_META_TIMEOUT = 15.0


# ── State token helpers ────────────────────────────────────────────────────────


def _state_signing_key() -> bytes:
    """Derive a signing key from APP_ENCRYPTION_KEY. Raises if unconfigured."""
    key = settings.app_encryption_key
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: APP_ENCRYPTION_KEY is not set.",
        )
    # Derive a distinct sub-key for state signing so it is decoupled from Fernet.
    return hashlib.sha256(f"nexbrain-signup-state:{key}".encode()).digest()


def create_embedded_signup_state(
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> str:
    """
    Create a stateless HMAC-signed state token encoding the signup context.

    Payload (JSON):
      { "u": user_id, "w": workspace_id, "a": agent_id, "exp": unix_ts, "nonce": hex }

    Token format: base64url(payload) + "." + hex(hmac-sha256)
    """
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=_STATE_TTL_SECONDS)).timestamp())
    payload = json.dumps(
        {
            "u": str(user_id),
            "w": str(workspace_id),
            "a": str(agent_id),
            "exp": exp,
            "nonce": secrets.token_hex(8),
        },
        separators=(",", ":"),
    )
    payload_b64 = payload.encode().hex()
    sig = hmac.new(_state_signing_key(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_embedded_signup_state(
    token: str,
    expected_user_id: uuid.UUID,
    expected_workspace_id: uuid.UUID,
) -> dict[str, Any]:
    """
    Verify the state token and return its payload.

    Raises HTTPException 400 for:
    - invalid format
    - invalid signature
    - expired token
    - user/workspace mismatch
    """
    try:
        payload_b64, sig = token.rsplit(".", 1)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_state")

    expected_sig = hmac.new(
        _state_signing_key(), payload_b64.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=400, detail="invalid_state")

    try:
        payload = json.loads(bytes.fromhex(payload_b64).decode())
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_state")

    now = int(datetime.now(timezone.utc).timestamp())
    if payload.get("exp", 0) < now:
        raise HTTPException(status_code=400, detail="expired_state")

    if payload.get("u") != str(expected_user_id):
        raise HTTPException(status_code=400, detail="invalid_state")
    if payload.get("w") != str(expected_workspace_id):
        raise HTTPException(status_code=400, detail="invalid_state")

    return payload


# ── Meta Graph API helpers ─────────────────────────────────────────────────────


def _meta_base_url() -> str:
    return f"https://graph.facebook.com/{settings.meta_graph_api_version}"


def _require_meta_config() -> tuple[str, str]:
    """Return (app_id, app_secret) or raise 503 if not configured."""
    app_id = settings.meta_app_id
    app_secret = settings.meta_app_secret
    if not app_id or not app_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="meta_config_missing",
        )
    return app_id, app_secret


def exchange_code_for_short_lived_token(code: str, redirect_uri: str | None = None) -> str:
    """Exchange Meta authorization code for a short-lived user access token.

    redirect_uri must match exactly what was passed to FB.login() on the frontend.
    Meta validates this to prevent code interception attacks.
    """
    app_id, app_secret = _require_meta_config()
    url = f"{_meta_base_url()}/oauth/access_token"
    params: dict[str, str] = {
        "client_id": app_id,
        "client_secret": app_secret,
        "code": code,
        "redirect_uri": redirect_uri if redirect_uri is not None else "",
    }
    try:
        resp = httpx.get(
            url,
            params=params,
            timeout=_META_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "meta_code_exchange failed status=%s body=%s",
            exc.response.status_code,
            _safe_meta_error(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_token_exchange_failed",
        ) from exc
    except httpx.RequestError as exc:
        logger.warning("meta_code_exchange request_error type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_token_exchange_failed",
        ) from exc

    token = data.get("access_token")
    if not token:
        logger.warning("meta_code_exchange missing access_token in response")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_token_exchange_failed",
        )
    return str(token)


def exchange_for_long_lived_token(short_lived_token: str) -> tuple[str, datetime | None]:
    """
    Exchange a short-lived user token for a long-lived one (~60 days).

    Returns (long_lived_token, expires_at | None).
    expires_at is None when Meta does not return an expires_in value.
    """
    app_id, app_secret = _require_meta_config()
    url = f"{_meta_base_url()}/oauth/access_token"
    try:
        resp = httpx.get(
            url,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_lived_token,
            },
            timeout=_META_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "meta_long_lived_exchange failed status=%s body=%s",
            exc.response.status_code,
            _safe_meta_error(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_token_exchange_failed",
        ) from exc
    except httpx.RequestError as exc:
        logger.warning("meta_long_lived_exchange request_error type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_token_exchange_failed",
        ) from exc

    token = data.get("access_token")
    if not token:
        logger.warning("meta_long_lived_exchange missing access_token in response")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_token_exchange_failed",
        )

    expires_at: datetime | None = None
    expires_in = data.get("expires_in")
    if expires_in:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            pass

    return str(token), expires_at


def fetch_waba_id_from_token(token: str) -> str:
    """
    Discover the WABA ID authorized by a user token via Meta's granular_scopes.

    Used when the frontend (Facebook Login for Business flow) does not provide
    waba_id via postMessage. The token's granular_scopes contain the WABA ID
    that the user explicitly selected during the popup flow.

    Raises HTTPException 422 if no WABA is found in the token scopes.
    Raises HTTPException 502 on Meta API errors.
    """
    url = f"{_meta_base_url()}/me"
    try:
        resp = httpx.get(
            url,
            params={"fields": "granular_scopes", "access_token": token},
            timeout=_META_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "fetch_waba_id_from_token failed status=%s body=%s",
            exc.response.status_code,
            _safe_meta_error(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_waba_discovery_failed",
        ) from exc
    except httpx.RequestError as exc:
        logger.warning("fetch_waba_id_from_token request_error type=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_waba_discovery_failed",
        ) from exc

    for scope_entry in data.get("granular_scopes", []):
        if scope_entry.get("scope") == "whatsapp_business_management":
            target_ids = scope_entry.get("target_ids", [])
            if target_ids:
                logger.info("fetch_waba_id_from_token discovered waba_id=%s", target_ids[0])
                return str(target_ids[0])

    logger.warning("fetch_waba_id_from_token no waba_id in granular_scopes data=%s", data)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="waba_not_found_in_token",
    )


def fetch_waba_phone_numbers(waba_id: str, token: str) -> list[dict[str, Any]]:
    """
    Fetch the phone numbers associated with a WhatsApp Business Account.

    Returns a list of phone number objects with fields:
      id, display_phone_number, verified_name, status, quality_rating
    """
    url = f"{_meta_base_url()}/{waba_id}/phone_numbers"
    try:
        resp = httpx.get(
            url,
            params={
                "fields": "id,display_phone_number,verified_name,status,quality_rating",
                "access_token": token,
            },
            timeout=_META_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "meta_waba_phone_numbers failed waba_id=%s status=%s body=%s",
            waba_id,
            exc.response.status_code,
            _safe_meta_error(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_waba_verification_failed",
        ) from exc
    except httpx.RequestError as exc:
        logger.warning(
            "meta_waba_phone_numbers request_error waba_id=%s type=%s",
            waba_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="meta_waba_verification_failed",
        ) from exc

    return data.get("data", [])


def _safe_meta_error(exc: httpx.HTTPStatusError) -> str:
    try:
        body = exc.response.json()
        msg = (body.get("error") or {}).get("message", "")
        if msg:
            return str(msg)[:200]
    except Exception:
        pass
    return exc.response.text[:200]


# ── Channel creation / update logic ───────────────────────────────────────────


def _find_channel_by_phone_number_id(
    db: Session,
    phone_number_id: str,
) -> Channel | None:
    return db.scalar(
        select(Channel).where(
            Channel.channel_type == "whatsapp",
            Channel.status != "archived",
            Channel.config_json["phone_number_id"].astext == phone_number_id,
        )
    )


def create_or_update_whatsapp_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    waba_id: str,
    phone_number_id: str,
    display_phone_number: str,
    business_id: str | None,
    long_lived_token: str,
    expires_at: datetime | None,
) -> ChannelOut:
    """
    Create or update the WhatsApp channel and its encrypted credential.

    Returns ChannelOut with the final channel state.

    Raises 409 if the phone_number_id is already connected to a different workspace.
    """
    existing = _find_channel_by_phone_number_id(db, phone_number_id)

    if existing is not None and existing.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="whatsapp_number_already_connected",
        )

    now = datetime.now(timezone.utc)
    channel_name = f"WhatsApp {display_phone_number}"

    config = {
        "provider": "meta_cloud_api",
        "onboarding_type": "embedded_signup",
        "waba_id": waba_id,
        "phone_number_id": phone_number_id,
        "display_phone_number": display_phone_number,
        "business_id": business_id,
        # access_token_ref is set after the credential is created
        "access_token_ref": None,
        "status": "active",
        "connected_at": now.isoformat(),
        "last_webhook_at": None,
        "auto_reply_enabled": False,
    }

    if existing is None:
        # Create new channel — public_key must be unique
        public_key = _generate_public_key("whatsapp")
        channel = Channel(
            workspace_id=workspace_id,
            agent_id=agent_id,
            channel_type="whatsapp",
            name=channel_name,
            public_key=public_key,
            status="active",
            config_json=config,
        )
        db.add(channel)
        db.flush()  # populate channel.id before creating credential
        logger.info(
            "embedded_signup channel created channel_id=%s workspace_id=%s phone_number_id=%s",
            channel.id,
            workspace_id,
            phone_number_id,
        )
    else:
        channel = existing
        channel.agent_id = agent_id
        channel.name = channel_name
        channel.config_json = {**channel.config_json, **config}
        channel.status = "active"
        channel.updated_at = now
        db.flush()
        logger.info(
            "embedded_signup channel updated channel_id=%s workspace_id=%s phone_number_id=%s",
            channel.id,
            workspace_id,
            phone_number_id,
        )

    # Create/update the encrypted credential
    cred = create_or_update_channel_credential(
        db,
        workspace_id=workspace_id,
        channel_id=channel.id,
        provider="meta_cloud_api",
        credential_type="whatsapp_user_access_token",
        plain_value=long_lived_token,
        obtained_via="embedded_signup",
        expires_at=expires_at,
        metadata_json={
            "waba_id": waba_id,
            "phone_number_id": phone_number_id,
            "business_id": business_id,
            "token_source": "embedded_signup",
        },
    )

    # Update channel with db: reference to the credential
    channel.config_json = {**channel.config_json, "access_token_ref": f"db:{cred.id}"}
    channel.updated_at = now

    db.commit()
    db.refresh(channel)

    logger.info(
        "embedded_signup complete channel_id=%s credential_id=%s",
        channel.id,
        cred.id,
    )
    return _channel_to_out(channel)


# ── Agent validation ───────────────────────────────────────────────────────────


def resolve_agent_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found in this workspace.",
        )
    return agent
