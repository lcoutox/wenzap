import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConversationFollowUp(Base):
    """
    Audit row for one follow-up sent (or claimed) on a conversation
    (follow-up-tool-prd.md) — also the concurrency guard for
    conversation_follow_up_scheduler.py.

    `silence_anchor` is a COPY of `Conversation.last_customer_message_at` at
    the moment this row was claimed, not a live reference — it identifies
    *which silence period* this send belongs to. The unique constraint on
    (conversation_id, step_order, silence_anchor) is what makes "claim this
    step" a single atomic DB operation: a second process racing to claim the
    same step for the same silence period gets an IntegrityError and backs
    off, no distributed lock needed. If the customer replies,
    last_customer_message_at moves forward, so counting "steps sent so far"
    against the *current* last_customer_message_at naturally excludes rows
    from a previous (now-stale) silence period — that's the whole
    cancellation mechanism, no explicit cancel logic required.

    `conversation_message_id` is NULL while the row is a pending claim (before
    the LLM call finishes) and set right before the transaction commits.
    """

    __tablename__ = "conversation_follow_ups"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "step_order", "silence_anchor",
            name="uq_conversation_follow_up_step_per_silence_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    silence_anchor: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conversation_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
