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
from app.models.pipeline_entry_stage_history import PipelineEntryStageHistory
from app.models.pipeline_stage import PipelineStage
from app.models.plan import Plan
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
from app.services import pipeline_webhook_service
from app.services.plan_feature_service import get_workspace_plan_code, workspace_allows_feature

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


def _check_pipelines_limit(db: Session, workspace_id: uuid.UUID) -> None:
    """Raises HTTP 402 if workspace has reached its plan's pipelines_limit."""
    plan_code = get_workspace_plan_code(db, workspace_id)
    plan = db.scalar(select(Plan).where(Plan.code == plan_code))
    if plan is None or plan.pipelines_limit <= 0:
        return  # 0/absent = unlimited

    active_count = db.scalar(
        select(func.count()).where(
            Pipeline.workspace_id == workspace_id,
            Pipeline.is_active.is_(True),
        )
    ) or 0

    if active_count >= plan.pipelines_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Pipeline limit reached for your plan ({plan.pipelines_limit} pipeline(s) "
                "allowed). Upgrade your plan or archive an existing pipeline to create a new one."
            ),
        )


def create_pipeline(db: Session, workspace_id: uuid.UUID, data: PipelineCreate) -> Pipeline:
    _check_pipelines_limit(db, workspace_id)
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


# ── Stage entry effects (Pipeline.2 Fase 1/4/5) ──────────────────────────────
#
# Shared by create_entry, move_entry and ensure_conversation_pipeline_entry —
# every path that puts an entry into a stage goes through here, so history,
# on_enter actions, removal-stage handling and the webhook always fire
# consistently regardless of who/what triggered the move.


def _record_stage_history(
    db: Session,
    workspace_id: uuid.UUID,
    entry: PipelineEntry,
    new_stage: PipelineStage | None,
    moved_by: str,
    now: datetime,
) -> None:
    # Close the currently-open history row for this entry, if any.
    open_row = db.scalar(
        select(PipelineEntryStageHistory).where(
            PipelineEntryStageHistory.entry_id == entry.id,
            PipelineEntryStageHistory.exited_at.is_(None),
        )
    )
    if open_row is not None:
        open_row.exited_at = now

    if new_stage is not None:
        db.add(
            PipelineEntryStageHistory(
                workspace_id=workspace_id,
                entry_id=entry.id,
                stage_id=new_stage.id,
                stage_name_snapshot=new_stage.name,
                entered_at=now,
                moved_by=moved_by,
            )
        )


def apply_stage_entry_effects(
    db: Session,
    workspace_id: uuid.UUID,
    entry: PipelineEntry,
    stage: PipelineStage,
    previous_stage_id: uuid.UUID | None,
    moved_by: str,
) -> None:
    """
    Apply everything that should happen when *entry* moves into *stage*:
    history (always), removal-stage status (always — manual causal effect,
    not gated), on_enter_* conversation actions + webhook (gated behind the
    pipeline_automations plan feature, same as entry_condition/stay_limit).
    """
    now = datetime.now(timezone.utc)
    _record_stage_history(db, workspace_id, entry, stage, moved_by, now)

    if stage.is_removal_stage:
        entry.status = "inactive"

    automations_enabled = workspace_allows_feature(db, workspace_id, "pipeline_automations")

    conversation: Conversation | None = None
    if automations_enabled and (
        stage.on_enter_conversation_status is not None
        or stage.on_enter_assigned_user_id is not None
        or stage.on_enter_ai_enabled is not None
    ):
        conversation = db.scalar(
            select(Conversation).where(Conversation.id == entry.conversation_id)
        )
        if conversation is not None:
            if stage.on_enter_conversation_status is not None:
                conversation.status = stage.on_enter_conversation_status
            if stage.on_enter_assigned_user_id is not None:
                conversation.assigned_user_id = stage.on_enter_assigned_user_id
            if stage.on_enter_ai_enabled is not None:
                conversation.ai_enabled = stage.on_enter_ai_enabled
            conversation.updated_at = now

    if automations_enabled and stage.webhook_url:
        try:
            pipeline_webhook_service.validate_webhook_url(stage.webhook_url)
        except pipeline_webhook_service.WebhookUrlError:
            pass  # invalid/unsafe URL — silently skip, already validated at save time
        else:
            if conversation is None:
                conversation = db.scalar(
                    select(Conversation).where(Conversation.id == entry.conversation_id)
                )
            contact = (
                db.scalar(select(Contact).where(Contact.id == entry.contact_id))
                if entry.contact_id
                else None
            )
            pipeline_webhook_service.dispatch_stage_entered_webhook(
                webhook_url=stage.webhook_url,
                webhook_auth_header=stage.webhook_auth_header,
                pipeline_id=stage.pipeline_id,
                stage_id=stage.id,
                stage_name=stage.name,
                entry_id=entry.id,
                conversation_id=entry.conversation_id,
                contact_id=entry.contact_id,
                contact_name=contact.name if contact else None,
                contact_phone=contact.phone if contact else None,
                previous_stage_id=previous_stage_id,
            )


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
    db.flush()

    if data.stage_id is not None:
        stage = db.scalar(select(PipelineStage).where(PipelineStage.id == data.stage_id))
        if stage is not None:
            apply_stage_entry_effects(db, workspace_id, entry, stage, None, "manual")

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
    stage = get_stage_or_404(db, workspace_id, pipeline_id, data.stage_id)
    previous_stage_id = entry.stage_id
    now = datetime.now(timezone.utc)
    entry.stage_id = data.stage_id
    entry.entered_stage_at = now
    entry.updated_at = now

    apply_stage_entry_effects(db, workspace_id, entry, stage, previous_stage_id, "manual")

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

    if stage_id is not None:
        stage = db.scalar(select(PipelineStage).where(PipelineStage.id == stage_id))
        if stage is not None:
            apply_stage_entry_effects(db, conversation.workspace_id, entry, stage, None, "initial")
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


# ── Stage history / metrics (Pipeline.2 Fase 5) ──────────────────────────────


def get_entry_stage_history(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    entry_id: uuid.UUID,
) -> list[PipelineEntryStageHistory]:
    _get_entry_or_404(db, workspace_id, pipeline_id, entry_id)
    return list(
        db.scalars(
            select(PipelineEntryStageHistory)
            .where(PipelineEntryStageHistory.entry_id == entry_id)
            .order_by(PipelineEntryStageHistory.entered_at.asc())
        ).all()
    )


def get_pipeline_metrics(db: Session, workspace_id: uuid.UUID, pipeline_id: uuid.UUID) -> dict:
    """
    Average time-in-stage (closed history rows only) and a simple conversion
    rate: entries that ever reached the last stage (by position) ÷ total
    entries ever created for this pipeline.
    """
    get_pipeline_or_404(db, workspace_id, pipeline_id)
    stages = list_stages(db, workspace_id, pipeline_id)

    stage_metrics = []
    for stage in stages:
        rows = db.scalars(
            select(PipelineEntryStageHistory).where(
                PipelineEntryStageHistory.stage_id == stage.id,
                PipelineEntryStageHistory.exited_at.is_not(None),
            )
        ).all()
        durations_minutes = [
            (row.exited_at - row.entered_at).total_seconds() / 60.0 for row in rows
        ]
        passed_through = db.scalar(
            select(func.count(func.distinct(PipelineEntryStageHistory.entry_id))).where(
                PipelineEntryStageHistory.stage_id == stage.id
            )
        ) or 0
        stage_metrics.append(
            {
                "stage_id": stage.id,
                "stage_name": stage.name,
                "avg_minutes_in_stage": (
                    sum(durations_minutes) / len(durations_minutes) if durations_minutes else None
                ),
                "entries_passed_through": passed_through,
            }
        )

    total_entries = db.scalar(
        select(func.count()).where(PipelineEntry.pipeline_id == pipeline_id)
    ) or 0

    entries_reached_last_stage = 0
    conversion_rate = None
    if stages:
        last_stage = stages[-1]
        entries_reached_last_stage = db.scalar(
            select(func.count(func.distinct(PipelineEntryStageHistory.entry_id))).where(
                PipelineEntryStageHistory.stage_id == last_stage.id
            )
        ) or 0
        if total_entries > 0:
            conversion_rate = entries_reached_last_stage / total_entries

    return {
        "stage_metrics": stage_metrics,
        "total_entries": total_entries,
        "entries_reached_last_stage": entries_reached_last_stage,
        "conversion_rate": conversion_rate,
    }
