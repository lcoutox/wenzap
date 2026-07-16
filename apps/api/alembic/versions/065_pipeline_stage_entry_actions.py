"""Add stage entry actions (on_enter_*) to pipeline_stages.

Pipeline.2 Fase 4 — actions applied to the conversation automatically when
an entry moves into a stage: status, human assignee, AI on/off.

Revision ID: 065
Revises: 064
Create Date: 2026-07-16
"""

import sqlalchemy as sa
from alembic import op

revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pipeline_stages",
        sa.Column("on_enter_conversation_status", sa.String(32), nullable=True),
    )
    op.add_column(
        "pipeline_stages",
        sa.Column("on_enter_assigned_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "pipeline_stages",
        sa.Column("on_enter_ai_enabled", sa.Boolean(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pipeline_stages_on_enter_assigned_user_id",
        "pipeline_stages",
        "users",
        ["on_enter_assigned_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_pipeline_stages_on_enter_assigned_user_id",
        "pipeline_stages",
        type_="foreignkey",
    )
    op.drop_column("pipeline_stages", "on_enter_ai_enabled")
    op.drop_column("pipeline_stages", "on_enter_assigned_user_id")
    op.drop_column("pipeline_stages", "on_enter_conversation_status")
