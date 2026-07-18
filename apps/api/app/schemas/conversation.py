import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.conversation import VALID_CONVERSATION_STATUSES


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
    handoff_reason: str | None = None
    resolution_summary: str | None = None
    assignment_reason: str | None = None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Attribution fields derived from Contact.metadata_json (web_widget only)
    source_page_url: str | None = None
    source_page_title: str | None = None
    source_referrer: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    last_seen_page_url: str | None = None
    last_seen_page_title: str | None = None

    model_config = ConfigDict(from_attributes=True)
