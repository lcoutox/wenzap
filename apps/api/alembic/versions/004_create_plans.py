"""create plans

Revision ID: 004
Revises: 003
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("monthly_price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="BRL"),
        sa.Column("agents_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("knowledge_bases_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("users_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("pipelines_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("integrations_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monthly_ai_credits", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("monthly_conversations", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )


def downgrade() -> None:
    op.drop_table("plans")
