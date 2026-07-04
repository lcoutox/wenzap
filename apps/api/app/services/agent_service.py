import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import AgentStatus, SubscriptionStatus
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.agent import AgentCreate, AgentOut, AgentUpdate, GuidedConfigSchema
from app.services.agent_avatar_service import get_avatar_url
from app.services.ai_model_service import (
    _get_workspace_plan_code,
    get_model_or_404,
    validate_model_for_plan,
)
from app.services.context_tier_service import plan_allows_context_tier, validate_context_tier

# Fields routed to agent_prompt_settings
_PROMPT_FIELDS = {"system_prompt", "persona", "response_style", "language_mode",
                  "knowledge_only", "show_sources",
                  "instructions_mode", "guided_config", "advanced_prompt",
                  "reply_delay_seconds"}

_VALID_REPLY_DELAYS: frozenset[int] = frozenset([0, 3, 5, 8, 15])

# Fields routed to agent_model_settings (handled explicitly, not via generic loop)
_MODEL_FIELDS = {"ai_model_id", "temperature", "context_tier"}

# Fields that can be explicitly cleared to None via PATCH
_CLEARABLE_FIELDS = {"description", "persona", "system_prompt", "guided_config", "advanced_prompt"}

# Valid status transitions
_VALID_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.draft:    {AgentStatus.active, AgentStatus.archived},
    AgentStatus.active:   {AgentStatus.inactive, AgentStatus.archived},
    AgentStatus.inactive: {AgentStatus.active, AgentStatus.archived},
    AgentStatus.archived: set(),
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_agent_or_404(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
    agent = db.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


def _get_prompt_settings(db: Session, agent_id: uuid.UUID) -> AgentPromptSettings | None:
    return db.scalar(
        select(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent_id)
    )


def _get_model_settings(db: Session, agent_id: uuid.UUID) -> AgentModelSettings | None:
    return db.scalar(
        select(AgentModelSettings).where(AgentModelSettings.agent_id == agent_id)
    )


def _get_or_create_prompt_settings(
    db: Session, agent: Agent
) -> AgentPromptSettings:
    """Return existing prompt settings or create from agent fields (transition fallback)."""
    ps = _get_prompt_settings(db, agent.id)
    if ps is None:
        ps = AgentPromptSettings(
            agent_id=agent.id,
            system_prompt=agent.system_prompt,
            persona=agent.persona,
        )
        db.add(ps)
        db.flush()
    return ps


def _get_or_create_model_settings(
    db: Session, agent: Agent
) -> AgentModelSettings | None:
    """Return existing model settings or create from agent fields (transition fallback).

    Returns None if agent.ai_model_id is not set — cannot create without a model FK.
    """
    ms = _get_model_settings(db, agent.id)
    if ms is None and agent.ai_model_id is not None:
        ms = AgentModelSettings(
            agent_id=agent.id,
            ai_model_id=agent.ai_model_id,
            model_name=agent.model_name,
            temperature=float(agent.temperature),
        )
        db.add(ms)
        db.flush()
    return ms


def _build_agent_out(
    agent: Agent,
    prompt: AgentPromptSettings | None,
    model_cfg: AgentModelSettings | None,
) -> AgentOut:
    """Compose AgentOut from agent + satellite settings, falling back to agent fields."""
    return AgentOut(
        id=agent.id,
        workspace_id=agent.workspace_id,
        name=agent.name,
        description=agent.description,
        status=AgentStatus(agent.status),
        system_prompt=prompt.system_prompt if prompt else agent.system_prompt,
        persona=prompt.persona if prompt else agent.persona,
        ai_model_id=model_cfg.ai_model_id if model_cfg else agent.ai_model_id,
        model_name=model_cfg.model_name if model_cfg else agent.model_name,
        temperature=float(model_cfg.temperature) if model_cfg else float(agent.temperature),
        catalog_enabled=agent.catalog_enabled,
        response_style=(prompt.response_style or "balanced") if prompt else "balanced",
        language_mode=(prompt.language_mode or "auto") if prompt else "auto",
        knowledge_only=prompt.knowledge_only if prompt else False,
        show_sources=prompt.show_sources if prompt else False,
        instructions_mode=(prompt.instructions_mode or "guided") if prompt else "guided",
        guided_config=prompt.guided_config if prompt else None,
        advanced_prompt=prompt.advanced_prompt if prompt else None,
        context_tier=(model_cfg.context_window_tier or "standard") if model_cfg else "standard",
        reply_delay_seconds=int(prompt.reply_delay_seconds) if prompt else 0,
        avatar_url=get_avatar_url(agent),
        avatar_mime_type=agent.avatar_mime_type,
        avatar_updated_at=agent.avatar_updated_at,
        created_by_user_id=agent.created_by_user_id,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _check_plan_limit(db: Session, workspace_id: uuid.UUID) -> None:
    """Raises HTTP 402 if workspace has reached agents_limit."""
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


# ── Public service functions ──────────────────────────────────────────────────

def list_agents(
    db: Session,
    workspace_id: uuid.UUID,
    status_filter: AgentStatus | None = None,
) -> list[AgentOut]:
    query = select(Agent).where(Agent.workspace_id == workspace_id)

    if status_filter is not None:
        query = query.where(Agent.status == status_filter.value)
    else:
        query = query.where(Agent.status != AgentStatus.archived.value)

    query = query.order_by(Agent.created_at.desc())
    agents = db.scalars(query).all()

    result = []
    for agent in agents:
        prompt = _get_prompt_settings(db, agent.id)
        model_cfg = _get_model_settings(db, agent.id)
        result.append(_build_agent_out(agent, prompt, model_cfg))
    return result


def get_agent(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> AgentOut:
    agent = _get_agent_or_404(db, workspace_id, agent_id)
    prompt = _get_prompt_settings(db, agent.id)
    model_cfg = _get_model_settings(db, agent.id)
    return _build_agent_out(agent, prompt, model_cfg)


def create_agent(
    db: Session,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: AgentCreate,
) -> AgentOut:
    _check_plan_limit(db, workspace_id)

    plan_code = _get_workspace_plan_code(db, workspace_id)
    model = get_model_or_404(db, data.ai_model_id)
    validate_model_for_plan(model, plan_code)

    # Create core agent record (legacy fields kept for transition compatibility)
    agent = Agent(
        workspace_id=workspace_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,   # transition: kept in agents
        persona=data.persona,               # transition: kept in agents
        ai_model_id=model.id,               # transition: kept in agents
        model_name=model.model_name,        # transition: kept in agents
        temperature=data.temperature,       # transition: kept in agents
        catalog_enabled=data.catalog_enabled,
        status=AgentStatus.draft.value,
        created_by_user_id=user_id,
    )
    db.add(agent)
    db.flush()  # get agent.id without committing

    # Create satellite settings in the same transaction
    prompt = AgentPromptSettings(
        agent_id=agent.id,
        system_prompt=data.system_prompt,
        persona=data.persona,
        response_style=data.response_style,
        language_mode=data.language_mode,
        knowledge_only=data.knowledge_only,
        show_sources=data.show_sources,
        reply_delay_seconds=5,  # new agents default to 5s debounce for better UX
    )
    db.add(prompt)

    model_cfg = AgentModelSettings(
        agent_id=agent.id,
        ai_model_id=model.id,
        model_name=model.model_name,
        temperature=data.temperature,
        context_window_tier="standard",
    )
    db.add(model_cfg)

    db.commit()
    db.refresh(agent)
    db.refresh(prompt)
    db.refresh(model_cfg)

    return _build_agent_out(agent, prompt, model_cfg)


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

    update_data = data.model_dump(exclude_unset=True)

    prompt = _get_or_create_prompt_settings(db, agent)
    model_cfg = _get_or_create_model_settings(db, agent)

    # ── Handle ai_model_id (implies model_name snapshot update) ──────────────
    if "ai_model_id" in update_data and update_data["ai_model_id"] is not None:
        plan_code = _get_workspace_plan_code(db, workspace_id)
        model = get_model_or_404(db, update_data["ai_model_id"])
        validate_model_for_plan(model, plan_code)

        # Write to satellite (primary source)
        if model_cfg is not None:
            model_cfg.ai_model_id = model.id
            model_cfg.model_name = model.model_name
        # Transition: keep agents in sync
        agent.ai_model_id = model.id
        agent.model_name = model.model_name

        del update_data["ai_model_id"]

    # ── Handle temperature ────────────────────────────────────────────────────
    if "temperature" in update_data and update_data["temperature"] is not None:
        temp_val = update_data.pop("temperature")
        if model_cfg is not None:
            model_cfg.temperature = temp_val
        agent.temperature = temp_val  # transition: keep agents in sync

    # ── Handle context_tier ───────────────────────────────────────────────────
    if "context_tier" in update_data and update_data["context_tier"] is not None:
        tier_val = update_data.pop("context_tier")
        if not validate_context_tier(tier_val):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid context_tier '{tier_val}'.",
            )
        plan_code = _get_workspace_plan_code(db, workspace_id)
        if not plan_allows_context_tier(plan_code, tier_val):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Este tamanho de contexto não está disponível no seu plano.",
            )
        if model_cfg is not None:
            model_cfg.context_window_tier = tier_val

    # ── Handle reply_delay_seconds ────────────────────────────────────────────
    if "reply_delay_seconds" in update_data and update_data["reply_delay_seconds"] is not None:
        delay_val = update_data.pop("reply_delay_seconds")
        if delay_val not in _VALID_REPLY_DELAYS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"reply_delay_seconds must be one of: {sorted(_VALID_REPLY_DELAYS)}.",
            )
        prompt.reply_delay_seconds = delay_val

    # ── Handle prompt fields ──────────────────────────────────────────────────
    for field in ("system_prompt", "persona", "response_style", "language_mode",
                  "knowledge_only", "show_sources",
                  "instructions_mode", "guided_config", "advanced_prompt"):
        if field not in update_data:
            continue
        value = update_data.pop(field)
        if value is None and field not in _CLEARABLE_FIELDS:
            continue
        # guided_config arrives as GuidedConfigSchema — store as plain dict (JSONB)
        if field == "guided_config" and isinstance(value, GuidedConfigSchema):
            value = value.model_dump()
        # Write to satellite (primary source)
        setattr(prompt, field, value)
        # Transition: keep legacy agent columns in sync for fields that exist there
        if hasattr(agent, field):
            setattr(agent, field, value)

    # ── Handle remaining agent fields (name, description) ────────────────────
    for field, value in update_data.items():
        if value is None and field not in _CLEARABLE_FIELDS:
            continue
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    if prompt:
        db.refresh(prompt)
    if model_cfg:
        db.refresh(model_cfg)

    return _build_agent_out(agent, prompt, model_cfg)


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
        prompt = _get_prompt_settings(db, agent.id)
        mode = (getattr(prompt, "instructions_mode", None) or "guided") if prompt else "guided"
        if mode == "advanced":
            adv = (getattr(prompt, "advanced_prompt", None) or "").strip()
            # Fallback to legacy system_prompt for agents migrated before UX.2
            if not adv:
                adv = (prompt.system_prompt or "").strip() if prompt else ""
            if not adv:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configure advanced_prompt before activating this agent.",
                )
        else:
            cfg = (getattr(prompt, "guided_config", None) or {}) if prompt else {}
            has_guided = cfg and any(
                v for v in cfg.values() if v is not None and v != [] and v != ""
            )
            legacy = (prompt.system_prompt or "").strip() if prompt else ""
            if not has_guided and not legacy:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Configure agent behavior before activating.",
                )

    agent.status = new_status.value
    db.commit()
    db.refresh(agent)

    prompt = _get_prompt_settings(db, agent.id)
    model_cfg = _get_model_settings(db, agent.id)
    return _build_agent_out(agent, prompt, model_cfg)


def archive_agent(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> AgentOut:
    agent = _get_agent_or_404(db, workspace_id, agent_id)

    if agent.status == AgentStatus.archived.value:
        prompt = _get_prompt_settings(db, agent.id)
        model_cfg = _get_model_settings(db, agent.id)
        return _build_agent_out(agent, prompt, model_cfg)

    agent.status = AgentStatus.archived.value
    db.commit()
    db.refresh(agent)

    prompt = _get_prompt_settings(db, agent.id)
    model_cfg = _get_model_settings(db, agent.id)
    return _build_agent_out(agent, prompt, model_cfg)
