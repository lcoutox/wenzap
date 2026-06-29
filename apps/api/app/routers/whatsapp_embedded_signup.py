"""
WhatsApp Embedded Signup endpoints — ES.2.

POST /channels/whatsapp/embedded-signup/state     — generate CSRF state token
POST /channels/whatsapp/embedded-signup/exchange  — exchange Meta code for token, create channel
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
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


def _require_write_role(
    db: Session,
    workspace: Workspace,
    user: User,
) -> None:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in _WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


@router.post("/state", response_model=WhatsAppEmbeddedSignupStateOut)
def create_state(
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
    _require_write_role(db, current_workspace, current_user)

    # Validate that the agent exists and belongs to this workspace
    signup_svc.resolve_agent_or_404(db, current_workspace.id, data.agent_id)

    state = signup_svc.create_embedded_signup_state(
        user_id=current_user.id,
        workspace_id=current_workspace.id,
        agent_id=data.agent_id,
    )
    return WhatsAppEmbeddedSignupStateOut(state=state, expires_in=600)


@router.post("/exchange", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def exchange(
    data: WhatsAppEmbeddedSignupExchangeRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ChannelOut:
    """
    Exchange a Meta authorization code for an access token and create/update the WhatsApp channel.

    Flow:
    1. Verify CSRF state (signature, expiry, user/workspace match).
    2. Exchange code → short-lived token via Meta Graph API.
    3. Exchange short-lived → long-lived token (~60 days).
    4. Verify phone_number_id belongs to waba_id via Meta Graph API.
    5. Create or update the WhatsApp Channel and its encrypted ChannelCredential.
    6. Return the channel.
    """
    _require_write_role(db, current_workspace, current_user)

    # 1. Verify state
    payload = signup_svc.verify_embedded_signup_state(
        token=data.state,
        expected_user_id=current_user.id,
        expected_workspace_id=current_workspace.id,
    )
    agent_id_str = payload.get("a")
    if not agent_id_str:
        raise HTTPException(status_code=400, detail="invalid_state")

    try:
        import uuid
        agent_id = uuid.UUID(agent_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_state")

    # Validate agent still exists in this workspace
    signup_svc.resolve_agent_or_404(db, current_workspace.id, agent_id)

    # 2. Exchange code → short-lived token
    logger.info(
        "embedded_signup exchange started workspace_id=%s waba_id=%s phone_number_id=%s",
        current_workspace.id,
        data.waba_id,
        data.phone_number_id,
    )
    short_lived_token = signup_svc.exchange_code_for_short_lived_token(data.code)

    # 3. Exchange short-lived → long-lived token
    long_lived_token, expires_at = signup_svc.exchange_for_long_lived_token(short_lived_token)

    # 4. Verify phone_number_id belongs to waba_id
    phone_numbers = signup_svc.fetch_waba_phone_numbers(data.waba_id, long_lived_token)
    matched = next(
        (p for p in phone_numbers if str(p.get("id")) == str(data.phone_number_id)),
        None,
    )
    if matched is None:
        logger.warning(
            "embedded_signup phone_number_id not found in waba "
            "waba_id=%s phone_number_id=%s workspace_id=%s",
            data.waba_id,
            data.phone_number_id,
            current_workspace.id,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="phone_number_not_found",
        )

    display_phone_number = matched.get("display_phone_number") or data.phone_number_id

    # 5. Create or update channel and credential
    return signup_svc.create_or_update_whatsapp_channel(
        db=db,
        workspace_id=current_workspace.id,
        agent_id=agent_id,
        waba_id=data.waba_id,
        phone_number_id=data.phone_number_id,
        display_phone_number=display_phone_number,
        business_id=data.business_id,
        long_lived_token=long_lived_token,
        expires_at=expires_at,
    )
