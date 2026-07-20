import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_RE = re.compile(r"^[+\d\s\(\)\-]{4,30}$")


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
    # How long (seconds) the agent waits after the visitor's last message before
    # replying — lets the widget avoid showing "typing" before the agent has
    # actually started composing anything.
    reply_delay_seconds: int
    # Contact capture settings
    contact_capture_enabled: bool
    require_name: bool
    require_email: bool
    require_phone: bool

    model_config = ConfigDict(from_attributes=False)


class WidgetPageContext(BaseModel):
    """Attribution data captured by widget.js from the embedding page."""

    page_url: str | None = Field(default=None, max_length=2048)
    page_title: str | None = Field(default=None, max_length=300)
    referrer: str | None = Field(default=None, max_length=2048)
    utm_source: str | None = Field(default=None, max_length=200)
    utm_medium: str | None = Field(default=None, max_length=200)
    utm_campaign: str | None = Field(default=None, max_length=200)
    utm_term: str | None = Field(default=None, max_length=200)
    utm_content: str | None = Field(default=None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def trim_and_nullify(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        cleaned: dict = {}
        for k, v in values.items():
            if isinstance(v, str):
                v = v.strip() or None
            cleaned[k] = v
        return cleaned


class WidgetSessionCreate(BaseModel):
    """Optional: visitor may include an existing token to resume a session."""

    session_token: str | None = None
    page_context: WidgetPageContext | None = None


class WidgetSessionOut(BaseModel):
    """Returned to the visitor — token plus contact_captured flag."""

    session_token: str
    contact_captured: bool

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


class ContactCaptureInput(BaseModel):
    """
    Visitor-supplied identity data for PATCH /public/widgets/{key}/session/contact.

    All fields are optional in the schema; the service validates which are
    required based on the channel's contact_capture config.
    """

    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("name must be at least 2 characters.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email format.")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not _PHONE_RE.match(v):
            raise ValueError(
                "phone must contain only digits, +, spaces, parentheses, or hyphens (4–30 chars)."
            )
        return v
