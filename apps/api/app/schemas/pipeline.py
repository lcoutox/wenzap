import uuid
from datetime import datetime

from pydantic import BaseModel  # noqa: TC002 — runtime use

# ── Pipeline ──────────────────────────────────────────────────────────────────

class PipelineCreate(BaseModel):
    name: str
    description: str | None = None
    show_inactive_conversations: bool = False


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    show_inactive_conversations: bool | None = None
    is_active: bool | None = None


class PipelineOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    is_active: bool
    show_inactive_conversations: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Pipeline Stage ────────────────────────────────────────────────────────────

class PipelineStageCreate(BaseModel):
    name: str
    description: str | None = None
    position: int
    assigned_agent_id: uuid.UUID | None = None
    entry_condition: str | None = None
    extra_prompt: str | None = None
    is_required: bool = False
    is_removal_stage: bool = False
    request_contact_info: bool = False
    stay_limit_enabled: bool = False
    stay_limit_minutes: int | None = None
    webhook_url: str | None = None
    webhook_auth_header: str | None = None
    on_enter_conversation_status: str | None = None
    on_enter_assigned_user_id: uuid.UUID | None = None
    on_enter_ai_enabled: bool | None = None


class PipelineStageUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    position: int | None = None
    assigned_agent_id: uuid.UUID | None = None
    entry_condition: str | None = None
    extra_prompt: str | None = None
    is_required: bool | None = None
    is_removal_stage: bool | None = None
    request_contact_info: bool | None = None
    stay_limit_enabled: bool | None = None
    stay_limit_minutes: int | None = None
    webhook_url: str | None = None
    webhook_auth_header: str | None = None
    on_enter_conversation_status: str | None = None
    on_enter_assigned_user_id: uuid.UUID | None = None
    on_enter_ai_enabled: bool | None = None


class PipelineStageOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    pipeline_id: uuid.UUID
    name: str
    description: str | None
    position: int
    assigned_agent_id: uuid.UUID | None
    entry_condition: str | None
    extra_prompt: str | None
    is_required: bool
    is_removal_stage: bool
    request_contact_info: bool
    stay_limit_enabled: bool
    stay_limit_minutes: int | None
    webhook_url: str | None
    webhook_auth_header: str | None
    on_enter_conversation_status: str | None
    on_enter_assigned_user_id: uuid.UUID | None
    on_enter_ai_enabled: bool | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StageReorderItem(BaseModel):
    id: uuid.UUID
    position: int


class StageReorderRequest(BaseModel):
    stages: list[StageReorderItem]


# ── Pipeline Entry ────────────────────────────────────────────────────────────

class PipelineEntryCreate(BaseModel):
    conversation_id: uuid.UUID
    stage_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    assigned_agent_id: uuid.UUID | None = None


class PipelineEntryMove(BaseModel):
    stage_id: uuid.UUID


class PipelineEntryOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    pipeline_id: uuid.UUID | None
    stage_id: uuid.UUID | None
    conversation_id: uuid.UUID
    contact_id: uuid.UUID | None
    assigned_agent_id: uuid.UUID | None
    status: str
    entered_stage_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Denormalized
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    conversation_status: str | None = None
    conversation_channel_type: str | None = None
    conversation_last_message_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Agent pipeline settings ───────────────────────────────────────────────────

class AgentPipelineSettingsUpdate(BaseModel):
    default_pipeline_id: uuid.UUID | None = None
    default_pipeline_stage_id: uuid.UUID | None = None


# ── Stage history / metrics (Pipeline.2 Fase 5) ──────────────────────────────

class PipelineEntryStageHistoryOut(BaseModel):
    id: uuid.UUID
    stage_id: uuid.UUID | None
    stage_name_snapshot: str
    entered_at: datetime
    exited_at: datetime | None
    moved_by: str

    model_config = {"from_attributes": True}


class PipelineStageMetric(BaseModel):
    stage_id: uuid.UUID
    stage_name: str
    avg_minutes_in_stage: float | None
    entries_passed_through: int


class PipelineMetricsOut(BaseModel):
    stage_metrics: list[PipelineStageMetric]
    total_entries: int
    entries_reached_last_stage: int
    conversion_rate: float | None
