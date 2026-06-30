import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="BRL")
    agents_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    knowledge_bases_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    sources_per_kb_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_source_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=50000)
    users_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    pipelines_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    integrations_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    catalog_items_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    channels_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    monthly_ai_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    monthly_conversations: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    max_file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
