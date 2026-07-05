import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WhatsappReviewMessage(Base):
    __tablename__ = "whatsapp_review_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("whatsapp_review_conversations.id", ondelete="SET NULL"), nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("whatsapp_review_contacts.id", ondelete="SET NULL"), nullable=True)

    meta_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # inbound | outbound
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")

    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # queued|sent|delivered|read|failed|received
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
