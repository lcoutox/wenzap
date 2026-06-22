import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import AgentStatus, SubscriptionStatus
from app.models.agent import Agent
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate

# Fields that can be explicitly cleared to None via PATCH.
# All other updatable fields are non-nullable and null is treated as "not sent".
_CLEARABLE_FIELDS = {"description", "persona", "system_prompt"}

# Valid status transitions: maps current status -> allowed next statuses
_VALID_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.draft:    {AgentStatus.active, AgentStatus.archived},
    AgentStatus.active:   {AgentStatus.inactive, AgentStatus.archived},
    AgentStatus.inactive: {AgentStatus.active, AgentStatus.archived},
    AgentStatus.archived: set(),  # terminal — no transitions allowed
}


def _get_agent_or_404(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
    agent = db.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


def _check_plan_limit(db: Session, workspace_id: uuid.UUID) -> None:
    """Raises HTTP 402 if workspace has no active subscription or has reached agents_limit."""
    sub = db.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id,
            WorkspaceSubscription.status == SubscriptionStatus.active.value,
        )
    )
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="No active subscription found for this workspace.",
        )

    plan = db.scalar(select(Plan).where(Plan.id == sub.plan_id))
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Subscription plan not found.",
        )

    # Archived agents do not count toward the limit
    active_count = db.scalar(
        select(func.count(Agent.id)).where(
            Agent.workspace_id == workspace_id,
            Agent.status != AgentStatus.archived.value,
        )
    )

    if (active_count or 0) >= plan.agents_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Agent limit reached for your plan ({plan.agents_limit} agent(s) allowed). "
                "Upgrade your plan or archive an existing agent to create a new one."
            ),
        )


def list_agents(
    db: Session,
    workspace_id: uuid.UUID,
    status_filter: AgentStatus | None = None,
) -> list[AgentOut]:
    query = select(Agent).where(Agent.workspace_id == workspace_id)

    if status_filter is not None:
        query = query.where(Agent.status == status_filter.value)
    else:
        # Default: exclude archived agents
        query = query.where(Agent.status != AgentStatus.archived.value)

    query = query.order_by(Agent.created_at.desc())
    agents = db.scalars(query).all()
    return [AgentOut.model_validate(a) for a in agents]


def get_agent(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> AgentOut:
    agent = _get_agent_or_404(db, workspace_id, agent_id)
    return AgentOut.model_validate(agent)


def create_agent(
    db: Session,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: AgentCreate,
) -> AgentOut:
    _check_plan_limit(db, workspace_id)

    agent = Agent(
        workspace_id=workspace_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        persona=data.persona,
        model_provider=data.model_provider,
        model_name=data.model_name,
        temperature=data.temperature,
        status=AgentStatus.draft.value,
        created_by_user_id=user_id,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)


def update_agent(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: AgentUpdate,
) -> AgentOut:
    agent = _get_agent_or_404(db, workspace_id, agent_id)

    if agent.status == AgentStatus.archived.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archived agents cannot be edited.",
        )

    # exclude_unset=True: only fields explicitly present in the JSON payload are included.
    # For clearable fields (description, persona, system_prompt): null means clear the field.
    # For non-clearable fields (name, model_provider, model_name, temperature): null is ignored.
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is None and field not in _CLEARABLE_FIELDS:
            continue
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)


def update_agent_status(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    new_status: AgentStatus,
) -> AgentOut:
    agent = _get_agent_or_404(db, workspace_id, agent_id)
    current = AgentStatus(agent.status)

    if new_status not in _VALID_TRANSITIONS[current]:
        if current == AgentStatus.archived:
            detail = "Archived agents cannot change status."
        else:
            detail = f"Cannot transition from '{current.value}' to '{new_status.value}'."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    if new_status == AgentStatus.active:
        if not agent.system_prompt or not agent.system_prompt.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="system_prompt is required to activate an agent.",
            )

    agent.status = new_status.value
    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)


def archive_agent(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> AgentOut:
    agent = _get_agent_or_404(db, workspace_id, agent_id)

    if agent.status == AgentStatus.archived.value:
        # Idempotent: already archived, return as-is
        return AgentOut.model_validate(agent)

    agent.status = AgentStatus.archived.value
    db.commit()
    db.refresh(agent)
    return AgentOut.model_validate(agent)
