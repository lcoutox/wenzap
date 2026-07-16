"""Evolution API provisioning endpoints — bridge WhatsApp provider (Slice 4).

POST /channels/whatsapp/evolution/connect              — create instance, return QR
GET  /channels/whatsapp/evolution/{channel_id}/status   — poll connection state
POST /channels/whatsapp/evolution/{channel_id}/disconnect

Mirrors the auth/role pattern of whatsapp_embedded_signup.py — owner/admin only.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.evolution_provisioning import (
    EvolutionConnectOut,
    EvolutionConnectRequest,
    EvolutionStatusOut,
)
from app.services import evolution_provisioning_service as evo_svc
from app.services.channel_service import get_channel_or_404
from app.services.whatsapp_embedded_signup_service import resolve_agent_or_404
from app.services.workspace_service import get_current_member_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/channels/whatsapp/evolution",
    tags=["whatsapp-evolution"],
    dependencies=[Depends(get_verified_user)],
)

_WRITE_ROLES = {MemberRole.owner, MemberRole.admin}


def _require_write_role(db: Session, workspace: Workspace, user: User) -> None:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in _WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissões insuficientes.",
        )


@router.post("/connect", response_model=EvolutionConnectOut, status_code=status.HTTP_201_CREATED)
def connect(
    data: EvolutionConnectRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> EvolutionConnectOut:
    """
    Create a new Evolution instance for this workspace/agent and return its QR code.

    The frontend should render qrcode_base64 and poll GET /{channel_id}/status
    until state == "open".
    """
    _require_write_role(db, current_workspace, current_user)
    resolve_agent_or_404(db, current_workspace.id, data.agent_id)

    logger.info(
        "evolution_connect_requested workspace_id=%s agent_id=%s user_id=%s",
        current_workspace.id,
        data.agent_id,
        current_user.id,
    )

    channel, qrcode_base64, pairing_code = evo_svc.provision_evolution_channel(
        db, current_workspace.id, data.agent_id
    )
    return EvolutionConnectOut(
        channel=channel, qrcode_base64=qrcode_base64, pairing_code=pairing_code
    )


@router.get("/{channel_id}/status", response_model=EvolutionStatusOut)
def get_status(
    channel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> EvolutionStatusOut:
    """Poll the Evolution instance connection state for this channel."""
    channel = get_channel_or_404(db, current_workspace.id, channel_id)
    state = evo_svc.check_evolution_connection_status(db, channel)
    return EvolutionStatusOut(channel_id=channel.id, state=state)


@router.post("/{channel_id}/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(
    channel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    """Archive the channel and best-effort delete the Evolution instance."""
    _require_write_role(db, current_workspace, current_user)
    channel = get_channel_or_404(db, current_workspace.id, channel_id)
    evo_svc.disconnect_evolution_channel(db, channel)
