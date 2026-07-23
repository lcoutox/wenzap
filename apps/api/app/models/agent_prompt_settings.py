import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentPromptSettings(Base):
    __tablename__ = "agent_prompt_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    persona: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_style: Mapped[str | None] = mapped_column(String(50), nullable=True)
    language_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    knowledge_only: Mapped[bool] = mapped_column(nullable=False, default=False)
    show_sources: Mapped[bool] = mapped_column(nullable=False, default=False)
    knowledge_fallback: Mapped[str | None] = mapped_column(String(30), nullable=True)
    instructions_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="guided")
    guided_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    advanced_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # whatsapp-voice-groq-elevenlabs-prd.md — reply with synthesized voice when
    # the triggering inbound message was itself a voice note. Requires the
    # workspace to have an ElevenLabs key configured; otherwise ignored.
    voice_reply_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    elevenlabs_voice_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
