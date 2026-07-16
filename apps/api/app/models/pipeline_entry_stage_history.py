import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineEntryStageHistory(Base):
    """
    One row per stage an entry has passed through — Pipeline.2 Fase 5.

    exited_at is null while the entry is still in this stage (the current row).
    stage_name_snapshot preserves the name even if the stage is later renamed
    or deleted (stage_id is ON DELETE SET NULL).
    """

    __tablename__ = "pipeline_entry_stage_history"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_entries.id", ondelete="CASCADE"), nullable=False
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True
    )
    stage_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # "initial" | "manual" | "entry_condition" | "stay_limit"
    moved_by: Mapped[str] = mapped_column(String(32), nullable=False)
