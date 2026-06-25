import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class WebWidgetConfig(BaseModel):
    """Validated config for channel_type='web_widget'."""

    model_config = ConfigDict(extra="forbid")

    theme: Literal["dark", "light", "auto"] = "dark"
    primary_color: str = "#6366f1"
    position: Literal["bottom-right", "bottom-left"] = "bottom-right"
    welcome_message: str = Field(default="Olá! Como posso ajudar?", max_length=500)
    header_title: str = Field(default="Atendimento", max_length=100)
    header_subtitle: str = Field(default="Resposta em segundos", max_length=200)
    placeholder: str = Field(default="Digite sua mensagem...", max_length=200)
    avatar_url: str | None = Field(default=None, max_length=2048)
    auto_open: bool = False
    auto_open_delay_seconds: int = Field(default=3, ge=0, le=60)

    # ── Visitor identity / lead capture ───────────────────────────────────────
    contact_capture_enabled: bool = False
    require_name: bool = False
    require_email: bool = False
    require_phone: bool = False

    @model_validator(mode="after")
    def validate_capture_has_at_least_one_field(self) -> "WebWidgetConfig":
        if self.contact_capture_enabled and not any(
            [self.require_name, self.require_email, self.require_phone]
        ):
            raise ValueError(
                "contact_capture_enabled requires at least one of "
                "require_name, require_email, or require_phone to be true."
            )
        return self

    @field_validator("primary_color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("primary_color must be a valid hex color (#RRGGBB)")
        return v

    @field_validator("avatar_url")
    @classmethod
    def validate_avatar_url(cls, v: str | None) -> str | None:
        if v is not None and not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("avatar_url must start with http:// or https://")
        return v


def _parse_web_widget_config(raw: dict | None) -> dict:
    """Validate and return a WebWidgetConfig dict, applying defaults."""
    cfg = WebWidgetConfig(**(raw or {}))
    return cfg.model_dump()


def _validate_allowed_origins(origins: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for o in origins:
        o = o.strip()
        if not o:
            raise ValueError("allowed_origins entries cannot be empty strings")
        if o in seen:
            continue
        seen.add(o)
        cleaned.append(o)
    return cleaned


class ChannelCreate(BaseModel):
    agent_id: uuid.UUID
    channel_type: str
    name: str = Field(min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)
    allowed_origins: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_config_and_origins(self) -> "ChannelCreate":
        # Only web_widget is implemented; future types rejected early.
        if self.channel_type != "web_widget":
            raise ValueError(
                f"channel_type '{self.channel_type}' is not yet implemented. "
                "Only 'web_widget' is supported."
            )
        self.config = _parse_web_widget_config(self.config)
        self.allowed_origins = _validate_allowed_origins(self.allowed_origins)
        return self


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict | None = None
    allowed_origins: list[str] | None = None
    status: Literal["active", "inactive"] | None = None

    @model_validator(mode="after")
    def validate_updatable_fields(self) -> "ChannelUpdate":
        if self.config is not None:
            # channel_type is not available here; service validates after resolving the channel.
            # We just run a basic config parse (web_widget defaults); service re-runs with type.
            self.config = _parse_web_widget_config(self.config)
        if self.allowed_origins is not None:
            self.allowed_origins = _validate_allowed_origins(self.allowed_origins)
        return self


class ChannelOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    agent_id: uuid.UUID
    channel_type: str
    name: str
    public_key: str
    status: str
    config: dict
    allowed_origins: list[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, channel: object) -> "ChannelOut":
        return cls(
            id=channel.id,  # type: ignore[attr-defined]
            workspace_id=channel.workspace_id,  # type: ignore[attr-defined]
            agent_id=channel.agent_id,  # type: ignore[attr-defined]
            channel_type=channel.channel_type,  # type: ignore[attr-defined]
            name=channel.name,  # type: ignore[attr-defined]
            public_key=channel.public_key,  # type: ignore[attr-defined]
            status=channel.status,  # type: ignore[attr-defined]
            config=channel.config_json or {},  # type: ignore[attr-defined]
            allowed_origins=channel.allowed_origins or [],  # type: ignore[attr-defined]
            created_at=channel.created_at,  # type: ignore[attr-defined]
            updated_at=channel.updated_at,  # type: ignore[attr-defined]
        )
