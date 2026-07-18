import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import AgentStatus, MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.agent import AgentCreate, AgentOut, AgentStatusUpdate, AgentUpdate
from app.schemas.agent_catalog_scope import AgentCatalogScopeOut, AgentCatalogScopeUpdate
from app.schemas.agent_follow_up import AgentFollowUpSettingsOut, AgentFollowUpSettingsUpdate
from app.schemas.agent_knowledge_base import (
    AgentKnowledgeBaseCreate,
    AgentKnowledgeBaseOut,
    AgentKnowledgeBaseUpdate,
)
from app.schemas.agent_test import AgentTestRequest, AgentTestResponse
from app.schemas.agent_tool import (
    AgentToolCreate,
    AgentToolOut,
    AgentToolUpdate,
    HttpToolTestRequest,
    HttpToolTestResponse,
)
from app.schemas.playground import (
    PlaygroundSessionCreate,
    PlaygroundSessionOut,
    PlaygroundSessionWithMessages,
)
from app.services import (
    agent_avatar_service,
    agent_catalog_scope_service,
    agent_follow_up_service,
    agent_knowledge_base_service,
    agent_service,
    agent_test_service,
    agent_tool_service,
    playground_service,
)
from app.services.plan_feature_service import workspace_allows_feature
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/agents", dependencies=[Depends(get_verified_user)])

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
            status_code=status.HTTP_403_FORBIDDEN, detail="Permissões insuficientes."
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


@router.delete("/{agent_id}/permanent", status_code=204)
def delete_agent_permanently(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_ARCHIVE_ROLES, db, current_workspace, current_user)
    agent_service.delete_agent_permanently(db, current_workspace.id, agent_id)


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


# ── Agent Tools (tool-calling) ────────────────────────────────────────────────

def _check_http_tools_feature(db: Session, workspace: Workspace) -> None:
    if not workspace_allows_feature(db, workspace.id, "http_tools"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "Ferramentas HTTP não estão disponíveis no seu plano atual. "
                "Faça upgrade para acessar este recurso."
            ),
        )


@router.get("/{agent_id}/tools/http", response_model=list[AgentToolOut])
def list_agent_http_tools(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[AgentToolOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return agent_tool_service.list_agent_tools(db, current_workspace.id, agent_id)


def _require_tool_type(data: AgentToolCreate, expected: str) -> None:
    """
    Each tool_type has its own create route (its own plan gate, or lack of
    one) — reject a mismatched tool_type here instead of trusting the client
    to pick the "correct" endpoint. Without this, POSTing an http_request
    body to /tools/request-human would create an HTTP tool while skipping
    _check_http_tools_feature's 402 gate entirely.
    """
    if data.tool_type != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"tool_type deve ser '{expected}' neste endpoint.",
        )


@router.post(
    "/{agent_id}/tools/http", response_model=AgentToolOut, status_code=status.HTTP_201_CREATED
)
def create_agent_http_tool(
    agent_id: uuid.UUID,
    data: AgentToolCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentToolOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    _require_tool_type(data, "http_request")
    _check_http_tools_feature(db, current_workspace)
    return agent_tool_service.create_agent_tool(db, current_workspace.id, agent_id, data)


@router.post("/{agent_id}/tools/http/test", response_model=HttpToolTestResponse)
def validate_agent_http_tool(
    agent_id: uuid.UUID,
    data: HttpToolTestRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> HttpToolTestResponse:
    """"Validar Configuração" — try a draft HTTP tool config before it's saved."""
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    _check_http_tools_feature(db, current_workspace)
    result = agent_tool_service.validate_http_tool_config(
        data.config.model_dump(), data.sample_input
    )
    return HttpToolTestResponse(**result)


@router.patch("/{agent_id}/tools/http/{tool_id}", response_model=AgentToolOut)
def update_agent_http_tool(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    data: AgentToolUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentToolOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_tool_service.update_agent_tool(
        db, current_workspace.id, agent_id, tool_id, data
    )


@router.delete("/{agent_id}/tools/http/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_http_tool(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    agent_tool_service.delete_agent_tool(db, current_workspace.id, agent_id, tool_id)


# Listing reuses GET /{agent_id}/tools/http above — list_agent_tools() already
# returns every tool_type for the agent, not just http_request ones.


@router.post(
    "/{agent_id}/tools/request-human",
    response_model=AgentToolOut,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_request_human_tool(
    agent_id: uuid.UUID,
    data: AgentToolCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentToolOut:
    # No feature gate — "Solicitar humano" is available on every plan (product
    # decision 2026-07-17: treated as a basic Inbox capability, same tier as
    # take-over/return-to-AI, not as premium automation like http_tools).
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    _require_tool_type(data, "request_human")
    return agent_tool_service.create_agent_tool(db, current_workspace.id, agent_id, data)


@router.patch("/{agent_id}/tools/request-human/{tool_id}", response_model=AgentToolOut)
def update_agent_request_human_tool(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    data: AgentToolUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentToolOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_tool_service.update_agent_tool(
        db, current_workspace.id, agent_id, tool_id, data
    )


@router.delete("/{agent_id}/tools/request-human/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_request_human_tool(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    agent_tool_service.delete_agent_tool(db, current_workspace.id, agent_id, tool_id)


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


# ── Avatar endpoints ───────────────────────────────────────────────────────────

@router.post("/{agent_id}/avatar", response_model=AgentOut)
async def upload_agent_avatar(
    agent_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    agent_obj = agent_service._get_agent_or_404(db, current_workspace.id, agent_id)
    file_data = await file.read()
    updated = agent_avatar_service.upload_avatar(
        db=db,
        agent=agent_obj,
        file_data=file_data,
        filename=file.filename or "avatar",
        content_type=file.content_type,
    )
    prompt = agent_service._get_prompt_settings(db, updated.id)
    model_cfg = agent_service._get_model_settings(db, updated.id)
    return agent_service._build_agent_out(updated, prompt, model_cfg)


@router.get("/{agent_id}/avatar/file")
def serve_agent_avatar(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Response:
    """Serve avatar bytes directly — fallback for local storage where file:// URLs are blocked."""
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    agent_obj = agent_service._get_agent_or_404(db, current_workspace.id, agent_id)
    data, mime = agent_avatar_service.read_avatar_bytes(agent_obj)
    return Response(content=data, media_type=mime, headers={"Cache-Control": "max-age=3600"})


@router.delete("/{agent_id}/avatar", response_model=AgentOut)
def delete_agent_avatar(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    agent_obj = agent_service._get_agent_or_404(db, current_workspace.id, agent_id)
    updated = agent_avatar_service.delete_avatar(db=db, agent=agent_obj)
    prompt = agent_service._get_prompt_settings(db, updated.id)
    model_cfg = agent_service._get_model_settings(db, updated.id)
    return agent_service._build_agent_out(updated, prompt, model_cfg)


# ── Catalog scope endpoints ────────────────────────────────────────────────────

@router.get("/{agent_id}/tools/catalog", response_model=AgentCatalogScopeOut)
def get_agent_catalog_scope(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentCatalogScopeOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return agent_catalog_scope_service.get_catalog_scope(
        db, agent_id=agent_id, workspace_id=current_workspace.id
    )


@router.put("/{agent_id}/tools/catalog", response_model=AgentCatalogScopeOut)
def update_agent_catalog_scope(
    agent_id: uuid.UUID,
    data: AgentCatalogScopeUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentCatalogScopeOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return agent_catalog_scope_service.update_catalog_scope(
        db, agent_id=agent_id, workspace_id=current_workspace.id, data=data
    )


# ── Follow-up endpoints ─────────────────────────────────────────────────────────

def _check_follow_up_feature(db: Session, workspace: Workspace) -> None:
    if not workspace_allows_feature(db, workspace.id, "follow_up"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "Follow-up automático não está disponível no seu plano atual. "
                "Faça upgrade para acessar este recurso."
            ),
        )


@router.get("/{agent_id}/follow-up", response_model=AgentFollowUpSettingsOut)
def get_agent_follow_up_settings(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentFollowUpSettingsOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return agent_follow_up_service.get_follow_up_settings(
        db, workspace_id=current_workspace.id, agent_id=agent_id
    )


@router.put("/{agent_id}/follow-up", response_model=AgentFollowUpSettingsOut)
def update_agent_follow_up_settings(
    agent_id: uuid.UUID,
    data: AgentFollowUpSettingsUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentFollowUpSettingsOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    # Only gate turning it ON / keeping it configured on — a downgraded
    # workspace must always be able to switch it off or edit while off,
    # same "never lock the operator out of disabling" rule as http_tools.
    if data.is_enabled:
        _check_follow_up_feature(db, current_workspace)
    return agent_follow_up_service.update_follow_up_settings(
        db, workspace_id=current_workspace.id, agent_id=agent_id, data=data
    )
