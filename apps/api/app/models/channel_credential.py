import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChannelCredential(Base):
    __tablename__ = "channel_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    # e.g. "meta_cloud_api"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g. "whatsapp_user_access_token"
    credential_type: Mapped[str] = mapped_column(String(80), nullable=False)
    # Fernet-encrypted value — never store or return plaintext
    encrypted_value: Mapped[str] = mapped_column(Text(), nullable=False)
    # Optional metadata: token_type, scopes, waba_id, etc.
    metadata_json: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    # NULL means the token has no known expiry (e.g. system user tokens)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # How the credential was obtained: "embedded_signup" | "manual" | "test"
    obtained_via: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships (lazy="raise" prevents accidental N+1 queries)
    channel: Mapped["Channel"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Channel", lazy="raise"
    )
    workspace: Mapped["Workspace"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Workspace", lazy="raise"
    )
