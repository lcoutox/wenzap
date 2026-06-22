import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.enums import AgentStatus, MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.agent import AgentCreate, AgentOut, AgentStatusUpdate, AgentUpdate
from app.services import agent_service
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/agents")

_READ_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member, MemberRole.viewer}
_WRITE_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member}
_ARCHIVE_ROLES = {MemberRole.owner, MemberRole.admin}


def _require_role(
    allowed: set[MemberRole],
    db: Session,
    workspace: Workspace,
    user: User,
) -> MemberRole:
    from fastapi import HTTPException

    role = get_current_member_role(db, workspace.id, user.id)
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    return role


@router.get("", response_model=list[AgentOut])
def list_agents(
    status_filter: Annotated[AgentStatus | None, Query(alias="status")] = None,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[AgentOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return agent_service.list_agents(db, current_workspace.id, status_filter)


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(
    data: AgentCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_service.create_agent(db, current_workspace.id, current_user.id, data)


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return agent_service.get_agent(db, current_workspace.id, agent_id)


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_service.update_agent(db, current_workspace.id, agent_id, data)


@router.patch("/{agent_id}/status", response_model=AgentOut)
def update_agent_status(
    agent_id: uuid.UUID,
    data: AgentStatusUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_service.update_agent_status(db, current_workspace.id, agent_id, data.status)


@router.delete("/{agent_id}", response_model=AgentOut)
def archive_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    _require_role(_ARCHIVE_ROLES, db, current_workspace, current_user)
    return agent_service.archive_agent(db, current_workspace.id, agent_id)
