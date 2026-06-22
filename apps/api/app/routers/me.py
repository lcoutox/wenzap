from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.user import UserOut
from app.schemas.workspace import WorkspaceOut
from app.services.workspace_service import get_current_member_role

router = APIRouter()


class MeOut(UserOut):
    workspace: WorkspaceOut
    role: MemberRole


@router.get("/me", response_model=MeOut)
def get_me(
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> MeOut:
    role = get_current_member_role(db, current_workspace.id, current_user.id)
    return MeOut(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        avatar_url=current_user.avatar_url,
        created_at=current_user.created_at,
        workspace=WorkspaceOut.model_validate(current_workspace),
        role=role,
    )
