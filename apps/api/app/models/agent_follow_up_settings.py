import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentFollowUpSettings(Base):
    """
    1:1 satellite of `agents` — whether/how the agent sends automatic
    re-engagement messages after the customer goes silent
    (follow-up-tool-prd.md). Escalating delay steps live in the sibling
    `agent_follow_up_steps` table (1:N), not here.
    """

    __tablename__ = "agent_follow_up_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Optional operator-written tone/instruction, applied to every step — the
    # model is already told which step number and how many hours elapsed, so
    # it varies escalation naturally without needing a per-step field.
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
