import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

VALID_CHANNEL_TYPES = {"web_widget", "whatsapp", "instagram", "email", "api"}
IMPLEMENTED_CHANNEL_TYPES = {"web_widget"}
VALID_CHANNEL_STATUSES = {"active", "inactive", "archived"}


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        CheckConstraint(
            "channel_type IN ('web_widget', 'whatsapp', 'instagram', 'email', 'api')",
            name="ck_channels_channel_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')",
            name="ck_channels_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    public_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    allowed_origins: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, default=list
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
