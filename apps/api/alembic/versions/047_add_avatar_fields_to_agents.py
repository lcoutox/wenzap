"""add avatar fields to agents

Revision ID: 047
Revises: 046
Create Date: 2026-07-01
"""

import sqlalchemy as sa

from alembic import op

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("avatar_file_key", sa.Text(), nullable=True))
    op.add_column("agents", sa.Column("avatar_mime_type", sa.String(50), nullable=True))
    op.add_column("agents", sa.Column("avatar_size_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "agents",
        sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "avatar_updated_at")
    op.drop_column("agents", "avatar_size_bytes")
    op.drop_column("agents", "avatar_mime_type")
    op.drop_column("agents", "avatar_file_key")
