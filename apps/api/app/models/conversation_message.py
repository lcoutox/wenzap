import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

VALID_DIRECTIONS = {"inbound", "outbound", "internal"}
VALID_SENDER_TYPES = {"customer", "human", "agent", "system"}

# Expected direction per sender_type (enforced in service layer, not DB):
#   customer  -> inbound
#   human     -> outbound | internal
#   agent     -> outbound
#   system    -> internal


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('inbound', 'outbound', 'internal')",
            name="ck_conv_messages_direction",
        ),
        CheckConstraint(
            "sender_type IN ('customer', 'human', 'agent', 'system')",
            name="ck_conv_messages_sender_type",
        ),
        # content_type has no check constraint intentionally — future types
        # (image, file, audio, system_event) should not require a migration.
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Set when a human user sends the message.
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Set when an AI agent sends the message.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    # Identifier from the external channel (e.g. WhatsApp message id).
    external_message_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # No updated_at — messages are immutable by design.
