import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkspaceCredential(Base):
    """
    Customer-supplied API key for a third-party service, scoped to the
    workspace (not a channel) — whatsapp-voice-groq-elevenlabs-prd.md.

    Unlike Anthropic/OpenAI (global keys in config.py, Wenzap-operated),
    Groq and ElevenLabs are billed per workspace by design: the customer
    brings their own key and pays their own usage directly.
    """

    __tablename__ = "workspace_credentials"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", name="uq_workspace_credentials_ws_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    # e.g. "groq" | "elevenlabs"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # Fernet-encrypted value — never store or return plaintext
    encrypted_value: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Workspace", lazy="raise"
    )
