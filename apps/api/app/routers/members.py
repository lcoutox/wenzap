import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.member import MemberOut, MemberRoleUpdate
from app.services.member_service import get_member_out, list_members, update_member_role
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/workspaces/current/members", dependencies=[Depends(get_verified_user)])


@router.get("", response_model=list[MemberOut])
def get_members(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[MemberOut]:
    return list_members(db, current_workspace.id)


@router.patch("/{member_id}/role", response_model=MemberOut)
def patch_member_role(
    member_id: uuid.UUID,
    data: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> MemberOut:
    requester_role = get_current_member_role(db, current_workspace.id, current_user.id)
    updated_id = update_member_role(db, current_workspace.id, member_id, data.role, requester_role)
    return get_member_out(db, current_workspace.id, updated_id)
