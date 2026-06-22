import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AiModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_model_providers.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    credits_per_message: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    min_plan_code: Mapped[str] = mapped_column(String(50), nullable=False, default="starter")
    context_window_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supports_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_tools: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_reasoning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supports_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
