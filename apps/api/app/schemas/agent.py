import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.enums import AgentStatus


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str | None = None
    persona: str | None = None
    ai_model_id: uuid.UUID
    temperature: float = 0.7
    catalog_enabled: bool = True

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name must not be empty.")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters.")
        return v

    @field_validator("system_prompt")
    @classmethod
    def system_prompt_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 8000:
            raise ValueError("System prompt must be at most 8000 characters.")
        return v

    @field_validator("persona")
    @classmethod
    def persona_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 1000:
            raise ValueError("Persona must be at most 1000 characters.")
        return v

    @field_validator("temperature")
    @classmethod
    def temperature_must_be_in_range(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0.")
        return v


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    persona: str | None = None
    ai_model_id: uuid.UUID | None = None
    temperature: float | None = None
    catalog_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Name must not be empty.")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters.")
        return v

    @field_validator("system_prompt")
    @classmethod
    def system_prompt_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 8000:
            raise ValueError("System prompt must be at most 8000 characters.")
        return v

    @field_validator("persona")
    @classmethod
    def persona_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 1000:
            raise ValueError("Persona must be at most 1000 characters.")
        return v

    @field_validator("temperature")
    @classmethod
    def temperature_must_be_in_range(cls, v: float | None) -> float | None:
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("temperature must be between 0.0 and 1.0.")
        return v


class AgentStatusUpdate(BaseModel):
    status: AgentStatus


class AgentOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: AgentStatus
    system_prompt: str | None
    persona: str | None
    ai_model_id: uuid.UUID | None
    model_name: str
    temperature: float
    catalog_enabled: bool
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
