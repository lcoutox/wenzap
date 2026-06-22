import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Possible values for AgentTestRun.status
# "success"  — LLM responded successfully; credits consumed
# "error"    — LLM was called but returned an error; credits NOT consumed
#
# Executions blocked BEFORE reaching the LLM (insufficient credits, unsupported
# model, wrong agent status, plan limit) are NOT recorded here by design.
# Only interactions that actually hit the provider are logged.


class AgentTestRun(Base):
    __tablename__ = "agent_test_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ai_model_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True
    )

    # Snapshots — preserved even if catalog entries change later
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    model_code: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Execution results
    credits_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # "success" | "error"
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # Sanitized error message from the provider (no stacktrace, no keys, no prompts)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
