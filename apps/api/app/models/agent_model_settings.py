import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentModelSettings(Base):
    __tablename__ = "agent_model_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # ai_model_id is NOT NULL — an agent always has a model.
    # ON DELETE RESTRICT: models must be deactivated (is_active=False), never deleted.
    ai_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_models.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Snapshot of ai_models.model_name at the time of selection.
    # Preserved for LLM API calls even if the catalog entry changes.
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.70)
    context_window_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    context_window_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
