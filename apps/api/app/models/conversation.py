import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

VALID_CONVERSATION_STATUSES = {"open", "pending", "resolved", "archived"}
VALID_CHANNEL_TYPES = {"internal", "web_widget", "whatsapp", "instagram", "email", "api"}


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'pending', 'resolved', 'archived')",
            name="ck_conversations_status",
        ),
        CheckConstraint(
            "channel_type IN ('internal', 'web_widget', 'whatsapp', 'instagram', 'email', 'api')",
            name="ck_conversations_channel_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    # Human user currently assigned to this conversation.
    # Service must validate that assigned_user_id has an active membership
    # in the workspace — FK alone does not enforce this.
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Channel that received/will deliver messages for this conversation.
    # Set on creation when channel is known (e.g. WhatsApp inbound). NULL for internal/legacy.
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("channels.id", ondelete="SET NULL"), nullable=True
    )
    channel_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="internal"
    )
    # Identifier of this conversation in the external channel (e.g. WhatsApp thread id).
    channel_external_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    # When False, the AI agent will not auto-reply (human has taken over).
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Reason captured from the model when the "request_human" tool paused the AI
    # (agent_tool_service.execute_request_human_tool). Cleared on return_to_ai() —
    # stale once the conversation is back with the AI. NULL for every other path
    # that disables ai_enabled (e.g. a human manually clicking "Assumir").
    handoff_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Updated by the message service each time a message is created.
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Updated ONLY when the new message is from the customer (sender_type="customer").
    # This is the anchor conversation_follow_up_scheduler.py measures silence from —
    # last_message_at alone can't be used for that, since our own follow-up sends
    # update it too, which would keep pushing the "how long has the customer been
    # quiet" clock forward every time we send one. NULL for conversations that
    # existed before this column was added, until their next customer message.
    last_customer_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
