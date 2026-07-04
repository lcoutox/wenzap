"""agent knowledge_fallback field

Revision ID: 060
Revises: 059
Create Date: 2026-07-04
"""

from alembic import op
import sqlalchemy as sa

revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_prompt_settings",
        sa.Column("knowledge_fallback", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_prompt_settings", "knowledge_fallback")
