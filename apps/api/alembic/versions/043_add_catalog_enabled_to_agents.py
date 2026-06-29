"""Add catalog_enabled to agents.

Revision ID: 043
Revises: 042
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "catalog_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "catalog_enabled")
