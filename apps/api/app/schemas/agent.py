import re
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.enums import AgentStatus

_PROVIDER_PATTERN = r"^[a-z0-9_-]+$"
_MODEL_NAME_PATTERN = r"^[a-zA-Z0-9._:-]+$"


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str | None = None
    persona: str | None = None
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-6"
    temperature: float = 0.7

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

    @field_validator("model_provider")
    @classmethod
    def provider_must_be_valid(cls, v: str) -> str:
        if not v or len(v) > 50:
            raise ValueError("model_provider must be between 1 and 50 characters.")
        if not re.match(_PROVIDER_PATTERN, v):
            raise ValueError(
                "model_provider must contain only lowercase letters, "
                "digits, hyphens and underscores."
            )
        return v

    @field_validator("model_name")
    @classmethod
    def model_name_must_be_valid(cls, v: str) -> str:
        if not v or len(v) > 100:
            raise ValueError("model_name must be between 1 and 100 characters.")
        if not re.match(_MODEL_NAME_PATTERN, v):
            raise ValueError(
                "model_name must contain only letters, digits, dots, "
                "underscores, hyphens and colons."
            )
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
    model_provider: str | None = None
    model_name: str | None = None
    temperature: float | None = None

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

    @field_validator("model_provider")
    @classmethod
    def provider_must_be_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v or len(v) > 50:
            raise ValueError("model_provider must be between 1 and 50 characters.")
        if not re.match(_PROVIDER_PATTERN, v):
            raise ValueError(
                "model_provider must contain only lowercase letters, "
                "digits, hyphens and underscores."
            )
        return v

    @field_validator("model_name")
    @classmethod
    def model_name_must_be_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v or len(v) > 100:
            raise ValueError("model_name must be between 1 and 100 characters.")
        if not re.match(_MODEL_NAME_PATTERN, v):
            raise ValueError(
                "model_name must contain only letters, digits, dots, "
                "underscores, hyphens and colons."
            )
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
    model_provider: str
    model_name: str
    temperature: float
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
