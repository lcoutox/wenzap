"""add is_public and sort_order to plans

Revision ID: 051
Revises: 050
Create Date: 2026-07-01

Adds two fields to `plans`:
  - is_public  : bool  — plan appears in UI/commercial listings
  - sort_order : int   — stable display order

Public plans (Free + Growth) are listed commercially.
Internal plans (Scale + Enterprise) exist for feature gates and
future commercial use but are not exposed in the UI.
"""

import sqlalchemy as sa
from alembic import op

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("is_public",   sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("plans", sa.Column("sort_order",  sa.Integer(), nullable=False, server_default="0"))

    # Mark public plans
    op.execute("UPDATE plans SET is_public = true,  sort_order = 10 WHERE code = 'starter'")
    op.execute("UPDATE plans SET is_public = true,  sort_order = 20 WHERE code = 'growth'")
    op.execute("UPDATE plans SET is_public = false, sort_order = 30 WHERE code = 'scale'")
    op.execute("UPDATE plans SET is_public = false, sort_order = 40 WHERE code = 'enterprise'")


def downgrade() -> None:
    op.drop_column("plans", "sort_order")
    op.drop_column("plans", "is_public")
