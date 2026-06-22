"""create usage counters

Revision ID: 006
Revises: 005
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_counters",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ai_credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conversations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "period_start"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("usage_counters")
