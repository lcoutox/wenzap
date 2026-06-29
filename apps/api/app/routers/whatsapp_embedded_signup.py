"""
WhatsApp Embedded Signup endpoints — ES.2 / ES.D1.

POST /channels/whatsapp/embedded-signup/state     — generate CSRF state token
POST /channels/whatsapp/embedded-signup/exchange  — exchange Meta code for token, create channel

Observability:
  The frontend sends X-Wenzap-Debug-Id on every request so all logs on both
  sides can be correlated by the same UUID for a given connection attempt.
"""

import logging
import uuid

import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.channel import ChannelOut
from app.schemas.whatsapp_embedded_signup import (
    WhatsAppEmbeddedSignupExchangeRequest,
    WhatsAppEmbeddedSignupStateOut,
    WhatsAppEmbeddedSignupStateRequest,
)
from app.services import whatsapp_embedded_signup_service as signup_svc
from app.services.workspace_service import get_current_member_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels/whatsapp/embedded-signup", tags=["whatsapp-embedded-signup"])

_WRITE_ROLES = {MemberRole.owner, MemberRole.admin}


def _require_write_role(db: Session, workspace: Workspace, user: User) -> None:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in _WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


def _debug_id(request: Request) -> str:
    """Extract debug correlation id from X-Wenzap-Debug-Id header (or empty string)."""
    return request.headers.get("x-wenzap-debug-id", "")


@router.post("/state", response_model=WhatsAppEmbeddedSignupStateOut)
def create_state(
    request: Request,
    data: WhatsAppEmbeddedSignupStateRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> WhatsAppEmbeddedSignupStateOut:
    """
    Generate a CSRF state token for the Embedded Signup flow.

    The state encodes user_id, workspace_id, agent_id and an expiry timestamp,
    signed with HMAC. The frontend must pass this state back to /exchange.
    """
    debug_id = _debug_id(request)
    _require_write_role(db, current_workspace, current_user)

    logger.info(
        "embedded_signup_state_requested debug_id=%s workspace_id=%s user_id=%s agent_id=%s",
        debug_id,
        current_workspace.id,
        current_user.id,
        data.agent_id,
    )

    signup_svc.resolve_agent_or_404(db, current_workspace.id, data.agent_id)

    state = signup_svc.create_embedded_signup_state(
        user_id=current_user.id,
        workspace_id=current_workspace.id,
        agent_id=data.agent_id,
    )

    logger.info("embedded_signup_state_created debug_id=%s", debug_id)
    return WhatsAppEmbeddedSignupStateOut(state=state, expires_in=600)


@router.post("/exchange", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def exchange(
    request: Request,
    data: WhatsAppEmbeddedSignupExchangeRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ChannelOut:
    """
    Exchange a Meta authorization code for an access token and create/update the WhatsApp channel.

    Flow:
    1. Verify CSRF state (signature, expiry, user/workspace match).
    2. Exchange code → short-lived token via Meta Graph API (no redirect_uri).
    3. Exchange short-lived → long-lived token (~60 days).
    4. Verify phone_number_id belongs to waba_id via Meta Graph API.
    5. Create or update the WhatsApp Channel and its encrypted ChannelCredential.
    6. Return the channel.
    """
    debug_id = _debug_id(request)
    _require_write_role(db, current_workspace, current_user)

    # Attach debug context to Sentry scope for this request
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("feature", "whatsapp_embedded_signup")
        scope.set_tag("debug_id", debug_id)
        scope.set_context("signup", {
            "debug_id": debug_id,
            "workspace_id": str(current_workspace.id),
            "waba_id": data.waba_id,
            "phone_number_id": data.phone_number_id,
        })

        return _do_exchange(data, debug_id, current_user, current_workspace, db)


def _do_exchange(
    data: WhatsAppEmbeddedSignupExchangeRequest,
    debug_id: str,
    current_user: User,
    current_workspace: Workspace,
    db: Session,
) -> ChannelOut:
    """Inner implementation — called inside Sentry scope."""

    # 1. Verify state
    logger.info(
        "embedded_signup_exchange_started debug_id=%s workspace_id=%s waba_id=%s phone=%s",
        debug_id,
        current_workspace.id,
        data.waba_id,
        data.phone_number_id,
    )

    payload = signup_svc.verify_embedded_signup_state(
        token=data.state,
        expected_user_id=current_user.id,
        expected_workspace_id=current_workspace.id,
    )
    agent_id_str = payload.get("a")
    if not agent_id_str:
        raise HTTPException(status_code=400, detail="invalid_state")

    try:
        agent_id = uuid.UUID(agent_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_state")

    signup_svc.resolve_agent_or_404(db, current_workspace.id, agent_id)
    logger.info("embedded_signup_state_validated debug_id=%s agent_id=%s", debug_id, agent_id)

    # 2. Exchange code → short-lived token
    logger.info("embedded_signup_meta_code_exchange_start debug_id=%s", debug_id)
    short_lived_token = signup_svc.exchange_code_for_short_lived_token(data.code, debug_id)
    logger.info("embedded_signup_meta_code_exchange_success debug_id=%s", debug_id)

    # 3. Exchange short-lived → long-lived token
    logger.info("embedded_signup_long_token_exchange_start debug_id=%s", debug_id)
    long_lived_token, expires_at = signup_svc.exchange_for_long_lived_token(
        short_lived_token, debug_id
    )

    # 4. Verify phone_number_id belongs to waba_id
    logger.info(
        "embedded_signup_phone_numbers_fetch_start debug_id=%s waba_id=%s",
        debug_id,
        data.waba_id,
    )
    phone_numbers = signup_svc.fetch_waba_phone_numbers(data.waba_id, long_lived_token, debug_id)
    matched = next(
        (p for p in phone_numbers if str(p.get("id")) == str(data.phone_number_id)),
        None,
    )
    if matched is None:
        logger.warning(
            "embedded_signup_phone_not_found debug_id=%s waba_id=%s phone=%s workspace_id=%s",
            debug_id,
            data.waba_id,
            data.phone_number_id,
            current_workspace.id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="phone_number_not_found",
        )

    display_phone_number = matched.get("display_phone_number") or data.phone_number_id
    logger.info(
        "embedded_signup_phone_number_verified debug_id=%s phone_number_id=%s",
        debug_id,
        data.phone_number_id,
    )

    # 5. Create or update channel and credential
    result = signup_svc.create_or_update_whatsapp_channel(
        db=db,
        workspace_id=current_workspace.id,
        agent_id=agent_id,
        waba_id=data.waba_id,
        phone_number_id=data.phone_number_id,
        display_phone_number=display_phone_number,
        business_id=data.business_id,
        long_lived_token=long_lived_token,
        expires_at=expires_at,
        debug_id=debug_id,
    )

    logger.info(
        "embedded_signup_completed debug_id=%s channel_id=%s workspace_id=%s",
        debug_id,
        result.id,
        current_workspace.id,
    )
    return result
