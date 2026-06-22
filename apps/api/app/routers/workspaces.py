from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceOut, WorkspaceUpdate
from app.services.workspace_service import get_current_member_role, update_workspace

router = APIRouter(prefix="/workspaces")


@router.get("/current", response_model=WorkspaceOut)
def get_current_workspace_route(
    current_workspace: Workspace = Depends(get_current_workspace),
) -> Workspace:
    return current_workspace


@router.patch("/current", response_model=WorkspaceOut)
def patch_current_workspace(
    data: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Workspace:
    role = get_current_member_role(db, current_workspace.id, current_user.id)
    return update_workspace(db, current_workspace, data, role)
