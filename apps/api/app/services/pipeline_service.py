"""Pipeline service — tenant-scoped CRUD for pipelines, stages and entries."""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.pipeline import Pipeline
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_stage import PipelineStage
from app.schemas.pipeline import (
    AgentPipelineSettingsUpdate,
    PipelineCreate,
    PipelineEntryCreate,
    PipelineEntryMove,
    PipelineStageCreate,
    PipelineStageUpdate,
    PipelineUpdate,
    StageReorderItem,
)

# ── Lookup helpers ────────────────────────────────────────────────────────────


def get_pipeline_or_404(db: Session, workspace_id: uuid.UUID, pipeline_id: uuid.UUID) -> Pipeline:
    pipeline = db.scalar(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.workspace_id == workspace_id,
        )
    )
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found.")
    return pipeline


def get_stage_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
) -> PipelineStage:
    stage = db.scalar(
        select(PipelineStage).where(
            PipelineStage.id == stage_id,
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.workspace_id == workspace_id,
        )
    )
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline stage not found."
        )
    return stage


def _get_entry_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> PipelineEntry:
    entry = db.scalar(
        select(PipelineEntry).where(
            PipelineEntry.id == entry_id,
            PipelineEntry.pipeline_id == pipeline_id,
            PipelineEntry.workspace_id == workspace_id,
        )
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline entry not found."
        )
    return entry


# ── Pipelines ─────────────────────────────────────────────────────────────────


def list_pipelines(db: Session, workspace_id: uuid.UUID) -> list[Pipeline]:
    return list(
        db.scalars(
            select(Pipeline)
            .where(Pipeline.workspace_id == workspace_id)
            .order_by(Pipeline.created_at.asc())
        ).all()
    )


def create_pipeline(db: Session, workspace_id: uuid.UUID, data: PipelineCreate) -> Pipeline:
    pipeline = Pipeline(
        workspace_id=workspace_id,
        name=data.name,
        description=data.description,
        show_inactive_conversations=data.show_inactive_conversations,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline


def update_pipeline(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    data: PipelineUpdate,
) -> Pipeline:
    pipeline = get_pipeline_or_404(db, workspace_id, pipeline_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pipeline, field, value)
    pipeline.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(pipeline)
    return pipeline


def delete_pipeline(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
) -> None:
    pipeline = get_pipeline_or_404(db, workspace_id, pipeline_id)
    active_count = db.scalar(
        select(func.count()).where(
            PipelineEntry.pipeline_id == pipeline_id,
            PipelineEntry.status == "active",
        )
    ) or 0
    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete pipeline with active entries.",
        )
    pipeline.is_active = False
    pipeline.updated_at = datetime.now(timezone.utc)
    db.commit()


# ── Stages ────────────────────────────────────────────────────────────────────


def list_stages(
    db: Session, workspace_id: uuid.UUID, pipeline_id: uuid.UUID
) -> list[PipelineStage]:
    get_pipeline_or_404(db, workspace_id, pipeline_id)
    return list(
        db.scalars(
            select(PipelineStage)
            .where(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.workspace_id == workspace_id,
            )
            .order_by(PipelineStage.position.asc())
        ).all()
    )


def create_stage(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    data: PipelineStageCreate,
) -> PipelineStage:
    get_pipeline_or_404(db, workspace_id, pipeline_id)

    if data.assigned_agent_id is not None:
        agent = db.scalar(
            select(Agent).where(
                Agent.id == data.assigned_agent_id,
                Agent.workspace_id == workspace_id,
            )
        )
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned agent not found in this workspace.",
            )

    stage = PipelineStage(
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        **data.model_dump(),
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
    data: PipelineStageUpdate,
) -> PipelineStage:
    stage = get_stage_or_404(db, workspace_id, pipeline_id, stage_id)

    if "assigned_agent_id" in data.model_fields_set and data.assigned_agent_id is not None:
        agent = db.scalar(
            select(Agent).where(
                Agent.id == data.assigned_agent_id,
                Agent.workspace_id == workspace_id,
            )
        )
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned agent not found in this workspace.",
            )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(stage, field, value)
    stage.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(stage)
    return stage


def reorder_stages(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    stages: list[StageReorderItem],
) -> list[PipelineStage]:
    get_pipeline_or_404(db, workspace_id, pipeline_id)
    now = datetime.now(timezone.utc)
    result: list[PipelineStage] = []
    for item in stages:
        stage = get_stage_or_404(db, workspace_id, pipeline_id, item.id)
        stage.position = item.position
        stage.updated_at = now
        result.append(stage)
    db.commit()
    for s in result:
        db.refresh(s)
    return sorted(result, key=lambda s: s.position)


def delete_stage(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
) -> None:
    stage = get_stage_or_404(db, workspace_id, pipeline_id, stage_id)
    active_count = db.scalar(
        select(func.count()).where(
            PipelineEntry.stage_id == stage_id,
            PipelineEntry.status == "active",
        )
    ) or 0
    if active_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete stage with active entries.",
        )
    db.delete(stage)
    db.commit()


# ── Entries ───────────────────────────────────────────────────────────────────


def list_entries(
    db: Session, workspace_id: uuid.UUID, pipeline_id: uuid.UUID
) -> list[dict]:
    get_pipeline_or_404(db, workspace_id, pipeline_id)
    rows = db.execute(
        select(
            PipelineEntry,
            Contact.name.label("contact_name"),
            Contact.phone.label("contact_phone"),
            Contact.email.label("contact_email"),
            Conversation.status.label("conversation_status"),
            Conversation.channel_type.label("conversation_channel_type"),
            Conversation.last_message_at.label("conversation_last_message_at"),
        )
        .outerjoin(Contact, PipelineEntry.contact_id == Contact.id)
        .outerjoin(Conversation, PipelineEntry.conversation_id == Conversation.id)
        .where(
            PipelineEntry.pipeline_id == pipeline_id,
            PipelineEntry.workspace_id == workspace_id,
        )
        .order_by(PipelineEntry.created_at.asc())
    ).all()

    result = []
    for row in rows:
        entry = row[0]
        result.append(
            {
                "id": entry.id,
                "workspace_id": entry.workspace_id,
                "pipeline_id": entry.pipeline_id,
                "stage_id": entry.stage_id,
                "conversation_id": entry.conversation_id,
                "contact_id": entry.contact_id,
                "assigned_agent_id": entry.assigned_agent_id,
                "status": entry.status,
                "entered_stage_at": entry.entered_stage_at,
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
                "contact_name": row.contact_name,
                "contact_phone": row.contact_phone,
                "contact_email": row.contact_email,
                "conversation_status": row.conversation_status,
                "conversation_channel_type": row.conversation_channel_type,
                "conversation_last_message_at": row.conversation_last_message_at,
            }
        )
    return result


def create_entry(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    data: PipelineEntryCreate,
) -> PipelineEntry:
    get_pipeline_or_404(db, workspace_id, pipeline_id)

    # Validate conversation belongs to workspace
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == data.conversation_id,
            Conversation.workspace_id == workspace_id,
        )
    )
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found."
        )

    # Validate stage belongs to pipeline if provided
    if data.stage_id is not None:
        get_stage_or_404(db, workspace_id, pipeline_id, data.stage_id)

    # Check unique constraint (pipeline_id, conversation_id)
    existing = db.scalar(
        select(PipelineEntry).where(
            PipelineEntry.pipeline_id == pipeline_id,
            PipelineEntry.conversation_id == data.conversation_id,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversation is already in this pipeline.",
        )

    now = datetime.now(timezone.utc)
    entry = PipelineEntry(
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        stage_id=data.stage_id,
        conversation_id=data.conversation_id,
        contact_id=data.contact_id if data.contact_id else conv.contact_id,
        assigned_agent_id=data.assigned_agent_id,
        status="active",
        entered_stage_at=now if data.stage_id else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def move_entry(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    entry_id: uuid.UUID,
    data: PipelineEntryMove,
) -> PipelineEntry:
    entry = _get_entry_or_404(db, workspace_id, pipeline_id, entry_id)
    # Validate stage belongs to this pipeline
    get_stage_or_404(db, workspace_id, pipeline_id, data.stage_id)
    entry.stage_id = data.stage_id
    entry.entered_stage_at = datetime.now(timezone.utc)
    entry.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(entry)
    return entry


def remove_entry(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> None:
    entry = _get_entry_or_404(db, workspace_id, pipeline_id, entry_id)
    entry.status = "removed"
    entry.updated_at = datetime.now(timezone.utc)
    db.commit()


# ── Auto-entry on conversation creation ──────────────────────────────────────


def ensure_conversation_pipeline_entry(db: Session, conversation: Conversation) -> None:
    """
    If the agent assigned to this conversation has a default_pipeline_id,
    create a pipeline entry automatically.

    Uses db.flush() not db.commit() — caller is responsible for committing.
    """
    if conversation.agent_id is None:
        return

    agent = db.scalar(select(Agent).where(Agent.id == conversation.agent_id))
    if agent is None or agent.default_pipeline_id is None:
        return

    pipeline_id = agent.default_pipeline_id
    stage_id = agent.default_pipeline_stage_id

    # Skip if entry already exists
    existing = db.scalar(
        select(PipelineEntry).where(
            PipelineEntry.pipeline_id == pipeline_id,
            PipelineEntry.conversation_id == conversation.id,
        )
    )
    if existing is not None:
        return

    now = datetime.now(timezone.utc)
    entry = PipelineEntry(
        workspace_id=conversation.workspace_id,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        conversation_id=conversation.id,
        contact_id=conversation.contact_id,
        assigned_agent_id=conversation.agent_id,
        status="active",
        entered_stage_at=now if stage_id else None,
    )
    db.add(entry)
    db.flush()


# ── Agent pipeline settings ───────────────────────────────────────────────────


def update_agent_pipeline_settings(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: AgentPipelineSettingsUpdate,
) -> Agent:
    agent = db.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")

    pipeline_id = data.default_pipeline_id
    stage_id = data.default_pipeline_stage_id

    if pipeline_id is not None:
        # Validate pipeline belongs to workspace
        pipeline = db.scalar(
            select(Pipeline).where(
                Pipeline.id == pipeline_id, Pipeline.workspace_id == workspace_id
            )
        )
        if pipeline is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Pipeline not found in this workspace.",
            )

        if stage_id is not None:
            stage = db.scalar(
                select(PipelineStage).where(
                    PipelineStage.id == stage_id,
                    PipelineStage.pipeline_id == pipeline_id,
                )
            )
            if stage is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Stage does not belong to the specified pipeline.",
                )
    else:
        # If no pipeline, stage should also be None
        if stage_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cannot set default_pipeline_stage_id without default_pipeline_id.",
            )

    agent.default_pipeline_id = pipeline_id
    agent.default_pipeline_stage_id = stage_id
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    return agent
