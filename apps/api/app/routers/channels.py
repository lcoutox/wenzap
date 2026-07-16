import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate
from app.services import channel_service
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/channels", dependencies=[Depends(get_verified_user)])

_READ_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member, MemberRole.viewer}
_WRITE_ROLES = {MemberRole.owner, MemberRole.admin}


def _require_role(
    allowed: set[MemberRole],
    db: Session,
    workspace: Workspace,
    user: User,
) -> MemberRole:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissões insuficientes.",
        )
    return role


@router.get("", response_model=list[ChannelOut])
def list_channels(
    channel_type: str | None = None,
    agent_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[ChannelOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return channel_service.list_channels(
        db,
        current_workspace.id,
        channel_type=channel_type,
        agent_id=agent_id,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def create_channel(
    data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ChannelOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return channel_service.create_channel(db, current_workspace.id, data)


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(
    channel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ChannelOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return channel_service.get_channel_detail(db, current_workspace.id, channel_id)


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(
    channel_id: uuid.UUID,
    data: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ChannelOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return channel_service.update_channel(db, current_workspace.id, channel_id, data)


@router.post("/{channel_id}/archive", response_model=ChannelOut)
def archive_channel(
    channel_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ChannelOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return channel_service.archive_channel(db, current_workspace.id, channel_id)
