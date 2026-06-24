
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicWidgetConfigOut(BaseModel):
    """Safe public config returned to any visitor — no internal IDs."""

    public_key: str
    name: str
    theme: str
    primary_color: str
    position: str
    welcome_message: str
    header_title: str
    header_subtitle: str
    placeholder: str
    avatar_url: str | None
    auto_open: bool
    auto_open_delay_seconds: int

    model_config = ConfigDict(from_attributes=False)


class WidgetSessionCreate(BaseModel):
    """Optional: visitor may include an existing token to resume a session."""

    session_token: str | None = None


class WidgetSessionOut(BaseModel):
    """Returned to the visitor — only the opaque token."""

    session_token: str

    model_config = ConfigDict(from_attributes=False)


class PublicWidgetMessageCreate(BaseModel):
    """Message body sent by a widget visitor."""

    content: str = Field(min_length=1, max_length=4000)

    def model_post_init(self, __context: object) -> None:
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("content cannot be blank.")


class PublicWidgetMessageOut(BaseModel):
    """Safe message representation returned to widget visitors."""

    id: uuid.UUID
    direction: str
    sender_type: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
