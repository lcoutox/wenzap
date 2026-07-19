"""
Agent Runs routes — "Auditoria" screen (execucoes-log-prd.md).

Read-only: lists ConversationAgentRun rows with contact/agent context and
the tool calls made inside each, so a workspace owner can see what their
agent actually did (and where it failed) without needing DB access.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.services import agent_run_service
from app.services.workspace_service import get_current_member_role

router = APIRouter(
    prefix="/agent-runs", tags=["Agent Runs"], dependencies=[Depends(get_verified_user)],
)

_READ_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member, MemberRole.viewer}


def _require_read(db: Session, workspace: Workspace, user: User) -> None:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in _READ_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permissões insuficientes.",
        )


@router.get("", response_model=list[dict])
def list_agent_runs(
    status_filter: str | None = Query(None, alias="status"),
    had_error: bool = Query(False),
    agent_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    tool_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[dict]:
    _require_read(db, current_workspace, current_user)
    return agent_run_service.list_agent_runs(
        db,
        current_workspace.id,
        status_filter=status_filter,
        had_error=had_error,
        agent_id=agent_id,
        conversation_id=conversation_id,
        tool_name=tool_name,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


@router.get("/{run_id}", response_model=dict)
def get_agent_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _require_read(db, current_workspace, current_user)
    result = agent_run_service.get_agent_run_detail(db, current_workspace.id, run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Execução não encontrada.",
        )
    return result
