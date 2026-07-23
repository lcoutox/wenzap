import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.enums import WorkspaceStatus

IntegrationProvider = Literal["groq", "elevenlabs"]

_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: WorkspaceStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None

    @field_validator("slug")
    @classmethod
    def slug_must_be_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re
        if not re.match(_SLUG_PATTERN, v):
            raise ValueError(
                "Slug must contain only lowercase letters, digits and hyphens, "
                "cannot start or end with a hyphen, and cannot have consecutive hyphens."
            )
        if len(v) < 3 or len(v) > 63:
            raise ValueError("Slug must be between 3 and 63 characters.")
        return v


class WorkspaceIntegrationsOut(BaseModel):
    """Never includes the actual key values — configured/not-configured only."""

    groq_configured: bool
    elevenlabs_configured: bool


class WorkspaceIntegrationKeyInput(BaseModel):
    api_key: str = Field(min_length=1, max_length=500)
