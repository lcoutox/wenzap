from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.workspace import (
    IntegrationProvider,
    WorkspaceIntegrationKeyInput,
    WorkspaceIntegrationsOut,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.services import workspace_credentials_service
from app.services.workspace_service import get_current_member_role, update_workspace

router = APIRouter(prefix="/workspaces")

_INTEGRATION_ROLES = {MemberRole.owner, MemberRole.admin}


def _require_integration_role(db: Session, workspace: Workspace, user: User) -> None:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in _INTEGRATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permissões insuficientes."
        )


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


@router.get("/current/integrations", response_model=WorkspaceIntegrationsOut)
def get_workspace_integrations(
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> WorkspaceIntegrationsOut:
    _require_integration_role(db, current_workspace, current_user)
    return WorkspaceIntegrationsOut(
        groq_configured=workspace_credentials_service.has_workspace_credential(
            db, current_workspace.id, "groq"
        ),
        elevenlabs_configured=workspace_credentials_service.has_workspace_credential(
            db, current_workspace.id, "elevenlabs"
        ),
    )


@router.put("/current/integrations/{provider}", response_model=WorkspaceIntegrationsOut)
def put_workspace_integration_key(
    provider: IntegrationProvider,
    data: WorkspaceIntegrationKeyInput,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> WorkspaceIntegrationsOut:
    _require_integration_role(db, current_workspace, current_user)
    workspace_credentials_service.set_workspace_credential(
        db, current_workspace.id, provider, data.api_key.strip()
    )
    return get_workspace_integrations(current_user, current_workspace, db)


@router.delete("/current/integrations/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_integration_key(
    provider: IntegrationProvider,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_integration_role(db, current_workspace, current_user)
    workspace_credentials_service.delete_workspace_credential(db, current_workspace.id, provider)
