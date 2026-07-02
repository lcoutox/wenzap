"""Pipelines router — tenant-scoped CRUD for pipelines, stages and entries."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_workspace, get_verified_user
from app.database import get_db
from app.models.workspace import Workspace
from app.schemas.agent import AgentOut
from app.schemas.pipeline import (
    AgentPipelineSettingsUpdate,
    PipelineCreate,
    PipelineEntryCreate,
    PipelineEntryMove,
    PipelineEntryOut,
    PipelineOut,
    PipelineStageCreate,
    PipelineStageOut,
    PipelineStageUpdate,
    PipelineUpdate,
    StageReorderRequest,
)
from app.services import pipeline_service
from app.services.agent_service import (
    _build_agent_out,
    _get_model_settings,
    _get_prompt_settings,
)
from app.services.plan_feature_service import workspace_allows_feature

router = APIRouter(dependencies=[Depends(get_verified_user)])


def _check_pipelines_feature(db: Session, workspace: Workspace) -> None:
    if not workspace_allows_feature(db, workspace.id, "pipelines"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
            "Pipelines are not available on your current plan. "
            "Upgrade to access this feature."
        ),
        )


# ── Pipelines ─────────────────────────────────────────────────────────────────


@router.get("/pipelines", response_model=list[PipelineOut])
def list_pipelines(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[PipelineOut]:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.list_pipelines(db, current_workspace.id)  # type: ignore[return-value]


@router.post("/pipelines", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    data: PipelineCreate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.create_pipeline(db, current_workspace.id, data)  # type: ignore[return-value]


@router.get("/pipelines/{pipeline_id}", response_model=PipelineOut)
def get_pipeline(
    pipeline_id: uuid.UUID,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.get_pipeline_or_404(db, current_workspace.id, pipeline_id)  # type: ignore[return-value]


@router.patch("/pipelines/{pipeline_id}", response_model=PipelineOut)
def update_pipeline(
    pipeline_id: uuid.UUID,
    data: PipelineUpdate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.update_pipeline(db, current_workspace.id, pipeline_id, data)  # type: ignore[return-value]


@router.delete("/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(
    pipeline_id: uuid.UUID,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Response:
    _check_pipelines_feature(db, current_workspace)
    pipeline_service.delete_pipeline(db, current_workspace.id, pipeline_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Stages ────────────────────────────────────────────────────────────────────


@router.get("/pipelines/{pipeline_id}/stages", response_model=list[PipelineStageOut])
def list_stages(
    pipeline_id: uuid.UUID,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[PipelineStageOut]:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.list_stages(db, current_workspace.id, pipeline_id)  # type: ignore[return-value]


@router.post(
    "/pipelines/{pipeline_id}/stages",
    response_model=PipelineStageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_stage(
    pipeline_id: uuid.UUID,
    data: PipelineStageCreate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineStageOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.create_stage(db, current_workspace.id, pipeline_id, data)  # type: ignore[return-value]


@router.post("/pipelines/{pipeline_id}/stages/reorder", response_model=list[PipelineStageOut])
def reorder_stages(
    pipeline_id: uuid.UUID,
    data: StageReorderRequest,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[PipelineStageOut]:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.reorder_stages(  # type: ignore[return-value]
        db, current_workspace.id, pipeline_id, data.stages
    )


@router.patch(
    "/pipelines/{pipeline_id}/stages/{stage_id}", response_model=PipelineStageOut
)
def update_stage(
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
    data: PipelineStageUpdate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineStageOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.update_stage(  # type: ignore[return-value]
        db, current_workspace.id, pipeline_id, stage_id, data
    )


@router.delete(
    "/pipelines/{pipeline_id}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_stage(
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Response:
    _check_pipelines_feature(db, current_workspace)
    pipeline_service.delete_stage(db, current_workspace.id, pipeline_id, stage_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Entries ───────────────────────────────────────────────────────────────────


@router.get("/pipelines/{pipeline_id}/entries", response_model=list[PipelineEntryOut])
def list_entries(
    pipeline_id: uuid.UUID,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[PipelineEntryOut]:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.list_entries(db, current_workspace.id, pipeline_id)  # type: ignore[return-value]


@router.post(
    "/pipelines/{pipeline_id}/entries",
    response_model=PipelineEntryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_entry(
    pipeline_id: uuid.UUID,
    data: PipelineEntryCreate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineEntryOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.create_entry(db, current_workspace.id, pipeline_id, data)  # type: ignore[return-value]


@router.patch("/pipelines/{pipeline_id}/entries/{entry_id}", response_model=PipelineEntryOut)
def update_entry(
    pipeline_id: uuid.UUID,
    entry_id: uuid.UUID,
    data: PipelineEntryMove,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineEntryOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.move_entry(  # type: ignore[return-value]
        db, current_workspace.id, pipeline_id, entry_id, data
    )


@router.post(
    "/pipelines/{pipeline_id}/entries/{entry_id}/move", response_model=PipelineEntryOut
)
def move_entry(
    pipeline_id: uuid.UUID,
    entry_id: uuid.UUID,
    data: PipelineEntryMove,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> PipelineEntryOut:
    _check_pipelines_feature(db, current_workspace)
    return pipeline_service.move_entry(  # type: ignore[return-value]
        db, current_workspace.id, pipeline_id, entry_id, data
    )


@router.delete(
    "/pipelines/{pipeline_id}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_entry(
    pipeline_id: uuid.UUID,
    entry_id: uuid.UUID,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> Response:
    _check_pipelines_feature(db, current_workspace)
    pipeline_service.remove_entry(db, current_workspace.id, pipeline_id, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Agent pipeline settings ───────────────────────────────────────────────────


@router.patch("/agents/{agent_id}/pipeline-settings", response_model=AgentOut)
def update_agent_pipeline_settings(
    agent_id: uuid.UUID,
    data: AgentPipelineSettingsUpdate,
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AgentOut:
    agent = pipeline_service.update_agent_pipeline_settings(
        db, current_workspace.id, agent_id, data
    )
    prompt = _get_prompt_settings(db, agent.id)
    model_cfg = _get_model_settings(db, agent.id)
    return _build_agent_out(agent, prompt, model_cfg)
