import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkspaceOnboardingProfile(Base):
    __tablename__ = "workspace_onboarding_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Personal
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)

    # Intent
    main_objective: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_monthly_conversations: Mapped[str] = mapped_column(String(50), nullable=False)
    ai_experience: Mapped[str] = mapped_column(String(50), nullable=False)

    # Company
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_industry: Mapped[str] = mapped_column(String(100), nullable=False)
    company_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False)

    # Origin & consent
    heard_from: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # State
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
