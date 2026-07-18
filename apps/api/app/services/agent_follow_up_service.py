"""
Agent Follow-up settings service — CRUD for the `agent_follow_up_settings` +
`agent_follow_up_steps` satellites (follow-up-tool-prd.md).

Unlike agent_tool_service.py, this has no LLM-facing schema/dispatch to
build — the actual follow-up generation+send logic lives in
conversation_follow_up_service.py, driven by conversation_follow_up_scheduler.py,
not by a model deciding to call something mid-turn.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_follow_up_settings import AgentFollowUpSettings
from app.models.agent_follow_up_step import AgentFollowUpStep
from app.schemas.agent_follow_up import AgentFollowUpSettingsOut, AgentFollowUpSettingsUpdate


def get_follow_up_settings(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID
) -> AgentFollowUpSettingsOut:
    _get_agent_or_404(db, workspace_id, agent_id)
    settings = _get_or_create_settings(db, workspace_id, agent_id)
    steps = _list_steps(db, agent_id)
    return AgentFollowUpSettingsOut(
        is_enabled=settings.is_enabled,
        custom_instructions=settings.custom_instructions,
        steps=list(steps),
    )


def update_follow_up_settings(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: AgentFollowUpSettingsUpdate,
) -> AgentFollowUpSettingsOut:
    _get_agent_or_404(db, workspace_id, agent_id)
    settings = _get_or_create_settings(db, workspace_id, agent_id)

    settings.is_enabled = data.is_enabled
    settings.custom_instructions = data.custom_instructions

    # Full replace — delete existing steps and insert the new ordered list.
    # Simpler and safer than diffing (no partial-order bugs), same approach
    # already used for the Pipeline stage reorder endpoint.
    db.query(AgentFollowUpStep).filter(AgentFollowUpStep.agent_id == agent_id).delete()
    for order, step in enumerate(data.steps):
        db.add(AgentFollowUpStep(
            workspace_id=workspace_id,
            agent_id=agent_id,
            step_order=order,
            delay_hours=step.delay_hours,
        ))

    db.commit()
    db.refresh(settings)
    steps = _list_steps(db, agent_id)
    return AgentFollowUpSettingsOut(
        is_enabled=settings.is_enabled,
        custom_instructions=settings.custom_instructions,
        steps=list(steps),
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_or_create_settings(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID
) -> AgentFollowUpSettings:
    settings = db.scalar(
        select(AgentFollowUpSettings).where(AgentFollowUpSettings.agent_id == agent_id)
    )
    if settings is None:
        settings = AgentFollowUpSettings(
            workspace_id=workspace_id, agent_id=agent_id, is_enabled=False
        )
        db.add(settings)
        db.flush()
    return settings


def _list_steps(db: Session, agent_id: uuid.UUID) -> list[AgentFollowUpStep]:
    return list(
        db.scalars(
            select(AgentFollowUpStep)
            .where(AgentFollowUpStep.agent_id == agent_id)
            .order_by(AgentFollowUpStep.step_order)
        ).all()
    )


def _get_agent_or_404(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
    agent = db.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado.")
    return agent
