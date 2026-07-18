import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentFollowUpStep(Base):
    """
    One escalating delay step in an agent's follow-up sequence
    (follow-up-tool-prd.md) — e.g. step_order=0/delay_hours=6, step_order=1/
    delay_hours=24. `step_order` is assigned from the operator's list order
    on save (0-indexed), not user-entered — `delay_hours` must be strictly
    increasing across a sequence, enforced in the service layer.
    """

    __tablename__ = "agent_follow_up_steps"
    __table_args__ = (
        UniqueConstraint("agent_id", "step_order", name="uq_agent_follow_up_step_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_hours: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
