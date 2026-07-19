import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Possible values for ConversationAgentRun.status:
# "success" — LLM responded; response saved; credits consumed
# "failed"  — LLM was called but errored, or pre-flight check failed after eligibility passed
# "skipped" — conversation was eligible but reply was intentionally skipped (e.g. rate limit)
# "blocked" — message blocked before LLM call (prompt injection, no credits, etc.)

VALID_CONVERSATION_AGENT_RUN_STATUSES = {"success", "failed", "skipped", "blocked"}


class ConversationAgentRun(Base):
    __tablename__ = "conversation_agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'failed', 'skipped', 'blocked')",
            name="ck_conv_agent_runs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    trigger_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False
    )
    response_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True
    )

    # One of: success | failed | skipped | blocked
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # True when the turn itself completed (status stays "success") but one
    # or more tool calls inside it failed (agent_tool_calls has a "status":
    # "error" entry) — orthogonal to `status`, which only reflects whether
    # the LLM turn crashed. Powers the "Execuções" log screen's failure
    # filter and the Inbox error indicator (execucoes-log-prd.md).
    had_tool_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Credit / token accounting
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # RAG metadata
    rag_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retrieved_chunks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retrieval_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error info (sanitized — no stacktraces, no prompts, no keys)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
