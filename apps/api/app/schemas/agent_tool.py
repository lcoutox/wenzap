import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class HttpToolConfig(BaseModel):
    """
    Config for tool_type="http_request". `method`/`url`/`headers` are fixed
    by whoever configures the tool in the UI; the model only ever supplies
    the dynamic `query_params`/`body` at call time (see
    agent_tool_service.build_tool_schema for the input_schema shown to the LLM).
    """

    method: HttpMethod = "GET"
    url: str = Field(min_length=1, max_length=1000)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=8, ge=1, le=15)


class AgentToolCreate(BaseModel):
    tool_type: Literal["http_request"]
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    description: str = Field(min_length=1, max_length=500)
    is_enabled: bool = True
    config: HttpToolConfig
    sort_order: int = 0


class AgentToolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_]+$")
    description: str | None = Field(default=None, min_length=1, max_length=500)
    is_enabled: bool | None = None
    config: HttpToolConfig | None = None
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
