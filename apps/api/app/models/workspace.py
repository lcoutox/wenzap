import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_org_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # True while *name* is still the signup-generated default ("Workspace de
    # {first_name}") — lets onboarding safely sync the collected company_name
    # into it. Flipped to False forever by any explicit rename
    # (workspace_service.update_workspace), so onboarding never clobbers a
    # deliberate choice.
    name_is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
