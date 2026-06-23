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
from app.schemas.agent_knowledge_base import (
    AgentKnowledgeBaseCreate,
    AgentKnowledgeBaseOut,
    AgentKnowledgeBaseUpdate,
)
from app.schemas.agent_test import AgentTestRequest, AgentTestResponse
from app.schemas.playground import (
    PlaygroundSessionCreate,
    PlaygroundSessionOut,
    PlaygroundSessionWithMessages,
)
from app.services import (
    agent_knowledge_base_service,
    agent_service,
    agent_test_service,
    playground_service,
)
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


# ── Playground Sessions ────────────────────────────────────────────────────────

@router.get(
    "/{agent_id}/playground/sessions",
    response_model=list[PlaygroundSessionOut],
)
def list_playground_sessions(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[PlaygroundSessionOut]:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    agent_service.get_agent(db, current_workspace.id, agent_id)  # validates ownership
    return playground_service.list_sessions(db, current_workspace.id, agent_id)


@router.post(
    "/{agent_id}/playground/sessions",
    response_model=PlaygroundSessionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_playground_session(
    agent_id: uuid.UUID,
    _data: PlaygroundSessionCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PlaygroundSessionOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    agent_service.get_agent(db, current_workspace.id, agent_id)  # validates ownership
    return playground_service.create_session(
        db, current_workspace.id, agent_id, current_user.id
    )


@router.get(
    "/{agent_id}/playground/sessions/{session_id}",
    response_model=PlaygroundSessionWithMessages,
)
def get_playground_session(
    agent_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PlaygroundSessionWithMessages:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    session, messages = playground_service.get_session_with_messages(
        db, current_workspace.id, agent_id, session_id
    )
    return PlaygroundSessionWithMessages(
        **PlaygroundSessionOut.model_validate(session).model_dump(),
        messages=messages,
    )


@router.delete(
    "/{agent_id}/playground/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_playground_session(
    agent_id: uuid.UUID,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    playground_service.delete_session(db, current_workspace.id, agent_id, session_id)


# ── Agent ↔ Knowledge Base connection ────────────────────────────────────────

@router.get("/{agent_id}/knowledge-bases", response_model=list[AgentKnowledgeBaseOut])
def list_agent_knowledge_bases(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[AgentKnowledgeBaseOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return agent_knowledge_base_service.list_agent_knowledge_bases(
        db, current_workspace.id, agent_id
    )


@router.post("/{agent_id}/knowledge-bases")
def connect_knowledge_base(
    agent_id: uuid.UUID,
    data: AgentKnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentKnowledgeBaseOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    out, created = agent_knowledge_base_service.connect_knowledge_base(
        db, current_workspace.id, agent_id, data.knowledge_base_id
    )
    from fastapi.responses import JSONResponse

    http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return JSONResponse(content=out.model_dump(mode="json"), status_code=http_status)


@router.patch("/{agent_id}/knowledge-bases/{kb_id}", response_model=AgentKnowledgeBaseOut)
def update_agent_knowledge_base(
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
    data: AgentKnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentKnowledgeBaseOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_knowledge_base_service.update_agent_knowledge_base(
        db, current_workspace.id, agent_id, kb_id, data
    )


@router.delete("/{agent_id}/knowledge-bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_knowledge_base(
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    agent_knowledge_base_service.disconnect_knowledge_base(
        db, current_workspace.id, agent_id, kb_id
    )


# ── Test endpoint ──────────────────────────────────────────────────────────────

@router.post("/{agent_id}/test", response_model=AgentTestResponse)
def test_agent(
    agent_id: uuid.UUID,
    data: AgentTestRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentTestResponse:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_test_service.run_agent_test(
        db,
        workspace_id=current_workspace.id,
        agent_id=agent_id,
        user_id=current_user.id,
        data=data,
    )
