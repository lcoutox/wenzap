"""Create pipeline_entry_stage_history table.

Pipeline.2 Fase 5 — records every stage a pipeline entry passes through,
with entered_at/exited_at, so we can compute time-in-stage metrics and
show a card timeline. Previously stage moves overwrote entry.stage_id with
no history at all.

Revision ID: 066
Revises: 065
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op

revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_entry_stage_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("entry_id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=True),
        sa.Column("stage_name_snapshot", sa.String(255), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("moved_by", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["pipeline_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], ["pipeline_stages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_entry_stage_history_entry_id",
        "pipeline_entry_stage_history",
        ["entry_id"],
    )
    op.create_index(
        "ix_pipeline_entry_stage_history_workspace_id",
        "pipeline_entry_stage_history",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pipeline_entry_stage_history_workspace_id",
        table_name="pipeline_entry_stage_history",
    )
    op.drop_index(
        "ix_pipeline_entry_stage_history_entry_id",
        table_name="pipeline_entry_stage_history",
    )
    op.drop_table("pipeline_entry_stage_history")
