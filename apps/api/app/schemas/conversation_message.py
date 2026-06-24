import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.conversation_message import VALID_DIRECTIONS, VALID_SENDER_TYPES

# Valid direction per sender_type.
_SENDER_ALLOWED_DIRECTIONS: dict[str, set[str]] = {
    "customer": {"inbound"},
    "human": {"outbound", "internal"},
    "agent": {"outbound"},
    "system": {"internal"},
}


class ConversationMessageCreate(BaseModel):
    content: str = Field(min_length=1)
    direction: str
    sender_type: str
    content_type: str = "text"
    sender_user_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    metadata: dict | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "ConversationMessageCreate":
        # Strip content.
        stripped = self.content.strip()
        if not stripped:
            raise ValueError("content cannot be blank.")
        self.content = stripped

        if self.content_type != "text":
            raise ValueError("content_type must be 'text' in this version.")

        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"direction must be one of: {', '.join(sorted(VALID_DIRECTIONS))}"
            )

        if self.sender_type not in VALID_SENDER_TYPES:
            raise ValueError(
                f"sender_type must be one of: {', '.join(sorted(VALID_SENDER_TYPES))}"
            )

        allowed = _SENDER_ALLOWED_DIRECTIONS[self.sender_type]
        if self.direction not in allowed:
            raise ValueError(
                f"sender_type '{self.sender_type}' requires direction to be "
                f"one of: {', '.join(sorted(allowed))}. Got '{self.direction}'."
            )

        return self


class ConversationMessageOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    sender_type: str
    sender_user_id: uuid.UUID | None
    agent_id: uuid.UUID | None
    content: str
    content_type: str
    external_message_id: str | None
    metadata_json: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
