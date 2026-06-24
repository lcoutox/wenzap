import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WidgetSession(Base):
    __tablename__ = "widget_sessions"
    __table_args__ = (
        UniqueConstraint("session_token", name="uq_widget_sessions_session_token"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized for fast queries without joining channels.
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    session_token: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
