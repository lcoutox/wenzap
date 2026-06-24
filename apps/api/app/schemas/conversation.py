import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.conversation import VALID_CHANNEL_TYPES, VALID_CONVERSATION_STATUSES


class ConversationCreate(BaseModel):
    contact_id: uuid.UUID | None = None
    contact_name: str | None = Field(default=None, min_length=1, max_length=300)
    agent_id: uuid.UUID | None = None
    channel_type: str = "internal"
    channel_external_id: str | None = None
    ai_enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def validate_contact_fields(cls, values: dict) -> dict:
        if not isinstance(values, dict):
            return values
        has_id = values.get("contact_id") is not None
        has_name = (values.get("contact_name") or "").strip() != ""
        if has_id and has_name:
            raise ValueError("Provide either contact_id or contact_name, not both.")
        if not has_id and not has_name:
            raise ValueError("Either contact_id or contact_name is required.")
        return values

    @model_validator(mode="after")
    def validate_channel_type(self) -> "ConversationCreate":
        if self.channel_type not in VALID_CHANNEL_TYPES:
            raise ValueError(
                f"channel_type must be one of: {', '.join(sorted(VALID_CHANNEL_TYPES))}"
            )
        return self


class ConversationUpdate(BaseModel):
    status: str | None = None
    agent_id: uuid.UUID | None = None
    assigned_user_id: uuid.UUID | None = None
    ai_enabled: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_ai_enabled(cls, values: dict) -> dict:
        # ai_enabled is boolean — null is not a valid value.
        if isinstance(values, dict) and "ai_enabled" in values and values["ai_enabled"] is None:
            raise ValueError("ai_enabled cannot be set to null; use true or false.")
        return values

    @model_validator(mode="after")
    def validate_status(self) -> "ConversationUpdate":
        if self.status is not None and self.status not in VALID_CONVERSATION_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(VALID_CONVERSATION_STATUSES))}"
            )
        return self


class ConversationOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    contact_id: uuid.UUID | None
    contact_name: str | None = None
    agent_id: uuid.UUID | None
    assigned_user_id: uuid.UUID | None
    channel_type: str
    channel_external_id: str | None
    status: str
    ai_enabled: bool
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
