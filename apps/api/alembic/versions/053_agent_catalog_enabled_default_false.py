"""Agent catalog_enabled default false.

Revision ID: 053
Revises: 052
Create Date: 2026-07-02
"""

from alembic import op
import sqlalchemy as sa

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change server default from true to false so new agents start with catalog disabled.
    op.alter_column(
        "agents",
        "catalog_enabled",
        server_default=sa.false(),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
    # Set all existing agents to false (catalog must be explicitly activated).
    op.execute("UPDATE agents SET catalog_enabled = false")


def downgrade() -> None:
    op.alter_column(
        "agents",
        "catalog_enabled",
        server_default=sa.true(),
        existing_type=sa.Boolean(),
        existing_nullable=False,
    )
