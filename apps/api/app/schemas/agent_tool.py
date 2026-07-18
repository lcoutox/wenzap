import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class HttpToolParam(BaseModel):
    """
    One named+described query parameter the operator has documented for an
    HTTP tool (http-tool-ux-improvements-prd.md). Turns the model-facing
    query_params schema from a generic untyped object into named, described
    properties — same spirit as path variables, but query params have no
    natural source of truth to infer them from (unlike {name} in the URL),
    so the operator lists them explicitly.
    """

    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str = Field(default="", max_length=300)
    required: bool = False


class HttpToolConfig(BaseModel):
    """
    Config for tool_type="http_request". `method`/`url`/`headers` are fixed
    by whoever configures the tool in the UI; the model only ever supplies
    the dynamic `query_params`/`body` at call time (see
    agent_tool_service.build_tool_schema for the input_schema shown to the LLM).

    `path_param_descriptions`/`query_params` are optional — every field here
    defaults to "no structured info", so tools created before
    http-tool-ux-improvements-prd.md keep working exactly as before (build_tool_schema
    falls back to the original generic schema when they're empty).
    """

    method: HttpMethod = "GET"
    url: str = Field(min_length=1, max_length=1000)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=8, ge=1, le=15)
    # {url placeholder name -> operator-written description}, shown to the LLM
    # instead of the generic "Value for 'x', used in the request URL." text.
    path_param_descriptions: dict[str, str] = Field(default_factory=dict)
    # Documented query params — when non-empty, build_tool_schema generates a
    # named/described nested schema instead of a freeform object.
    query_params: list[HttpToolParam] = Field(default_factory=list)


class HttpToolTestRequest(BaseModel):
    """POST /agents/{id}/tools/http/test — validate a draft config before saving."""

    config: HttpToolConfig
    sample_input: dict = Field(default_factory=dict)


class HttpToolTestResponse(BaseModel):
    ok: bool
    status_code: int | None = None
    body: str | None = None
    error: str | None = None


class RequestHumanToolConfig(BaseModel):
    """
    Config for tool_type="request_human". No configurable fields — matches
    the market convention (Chatvolt's own Request Human Tool) of a pure
    enable/disable toggle; the model-facing behavior is driven entirely by
    the tool's `name`/`description`, same as every other AgentTool row.
    `extra="forbid"` matters here: it's what lets Pydantic's smart union
    correctly reject an http_request config (which always has a `url`) from
    being parsed as this type, and vice versa.
    """

    model_config = ConfigDict(extra="forbid")


class MarkResolvedToolConfig(BaseModel):
    """
    Config for tool_type="mark_resolved". No configurable fields — same
    pure-toggle shape as RequestHumanToolConfig; the model-facing behavior
    is driven entirely by the tool's `name`/`description`.

    NOTE: this is structurally identical to RequestHumanToolConfig (both
    empty, both extra="forbid") — Pydantic's smart union can resolve an
    incoming `{}` to *either* class regardless of which tool_type it's
    actually for, since both accept exactly the same (empty) input. That's
    harmless here (they behave identically either way), but means
    agent_tool_service._validate_tool_config must NOT isinstance-check
    against one specific empty-config class — check membership in "any
    empty-config type" instead. Only HttpToolConfig (which requires `url`)
    is reliably distinguishable from the other two.
    """

    model_config = ConfigDict(extra="forbid")


AgentToolConfig = HttpToolConfig | RequestHumanToolConfig | MarkResolvedToolConfig


class AgentToolCreate(BaseModel):
    tool_type: Literal["http_request", "request_human", "mark_resolved"]
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    description: str = Field(min_length=1, max_length=500)
    is_enabled: bool = True
    config: AgentToolConfig = Field(default_factory=RequestHumanToolConfig)
    sort_order: int = 0


class AgentToolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    description: str | None = Field(default=None, min_length=1, max_length=500)
    is_enabled: bool | None = None
    config: AgentToolConfig | None = None
    sort_order: int | None = None


class AgentToolOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    agent_id: uuid.UUID
    tool_type: str
    name: str
    description: str
    is_enabled: bool
    config: dict
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
