"""add logo_url to ai_model_providers

Revision ID: 013
Revises: 012
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_model_providers",
        sa.Column("logo_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_model_providers", "logo_url")
