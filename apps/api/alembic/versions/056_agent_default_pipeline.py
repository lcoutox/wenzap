"""Add default_pipeline_id and default_pipeline_stage_id to agents.

Revision ID: 056
Revises: 055
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("default_pipeline_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("default_pipeline_stage_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agents_default_pipeline_id",
        "agents",
        "pipelines",
        ["default_pipeline_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_agents_default_pipeline_stage_id",
        "agents",
        "pipeline_stages",
        ["default_pipeline_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agents_default_pipeline_stage_id", "agents", type_="foreignkey")
    op.drop_constraint("fk_agents_default_pipeline_id", "agents", type_="foreignkey")
    op.drop_column("agents", "default_pipeline_stage_id")
    op.drop_column("agents", "default_pipeline_id")
