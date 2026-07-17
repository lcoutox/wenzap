import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentToolCall(Base):
    """
    Audit row for one LLM round-trip within an agent turn's tool-calling loop.

    One row per round-trip (not per tool execution) — `input_tokens`/
    `output_tokens`/`duration_ms` are that round-trip's real cost, so summing
    them across a turn's rows always equals what was actually billed. A round
    with no tool_use (a plain reply, or the final answer after earlier tool
    rounds) still gets a row, with `tool_calls` as an empty list.

    `tool_calls` is JSONB because Anthropic allows a model to request several
    tools in parallel within a single response — one round-trip can carry
    more than one tool execution, so a single scalar tool-name column would
    lose data. Same "config in JSONB, not a column per tool type" rationale
    as `AgentTool.config`.

    Attaches to exactly one of `conversation_agent_run_id` (production Inbox/
    WhatsApp replies) or `agent_test_run_id` (Playground) — never both, never
    neither. Not enforced with a DB CHECK constraint (kept simple, matching
    this module's other satellites); both call sites that write this table
    guarantee the invariant.
    """

    __tablename__ = "agent_tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    conversation_agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversation_agent_runs.id", ondelete="CASCADE"), nullable=True
    )
    agent_test_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_test_runs.id", ondelete="CASCADE"), nullable=True
    )

    call_index: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    # [{"tool_name", "tool_use_id", "input", "output", "status"}, ...] — [] if none.
    tool_calls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
