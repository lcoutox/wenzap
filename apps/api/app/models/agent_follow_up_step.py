import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentFollowUpStep(Base):
    """
    One escalating delay step in an agent's follow-up sequence
    (follow-up-tool-prd.md) — e.g. step_order=0/delay_hours=6, step_order=1/
    delay_hours=24. `step_order` is assigned from the operator's list order
    on save (0-indexed), not user-entered — `delay_hours` must be strictly
    increasing across a sequence, enforced in the service layer.

    `custom_instructions` (adendo, follow-up-tool-prd.md) is optional and
    specific to THIS step — combined with (not replacing)
    AgentFollowUpSettings.custom_instructions, which is general/applies to
    every step. Left blank, a step just relies on the general instruction
    (or none) plus the step-number/hours-elapsed context already given to
    the model — this field only matters when a step needs to say something
    the general instruction can't (e.g. "offer a 10% discount code").
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
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
