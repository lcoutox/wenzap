import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    # None means "not provided" (field absent from request body via exclude_unset).
    # An explicit null in the JSON is rejected by the validator below.
    name: str | None = Field(default=None, min_length=1, max_length=200)
    # Explicit None clears description; absent field leaves it unchanged.
    description: str | None = None

    @model_validator(mode="after")
    def name_cannot_be_null(self) -> "KnowledgeBaseUpdate":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be set to null")
        return self


class KnowledgeBaseOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
