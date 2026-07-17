import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentTool(Base):
    """
    A tool an agent can call during a conversation (Anthropic tool-calling).

    1:N satellite of `agents`, per the module's established "small stable
    parent + satellite tables" pattern — an agent can have several tools.

    `name` is what the LLM sees as the tool's identifier and MUST be unique
    per agent (the Anthropic API rejects duplicate tool names in one request,
    and the executor's tool_dispatch map is keyed on it). `description` is
    the other model-facing field — kept short and action-oriented so the LLM
    knows when to use it (same guidance Chatvolt's own docs give).

    `tool_type` is the discriminator for which built-in implementation
    executes this row (currently only "http_request"); `config` holds the
    type-specific settings (method/url/headers for an HTTP tool) as JSONB
    instead of one column per possible tool type.
    """

    __tablename__ = "agent_tools"
    __table_args__ = (
        UniqueConstraint("agent_id", "name", name="uq_agent_tool_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )

    tool_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
