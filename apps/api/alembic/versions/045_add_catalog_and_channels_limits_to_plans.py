"""add catalog_items_limit and channels_limit to plans

Revision ID: 045
Revises: 044
Create Date: 2026-06-30
"""

import sqlalchemy as sa

from alembic import op

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("catalog_items_limit", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "plans",
        sa.Column("channels_limit", sa.Integer(), nullable=False, server_default="1"),
    )

    # Set sensible values per plan tier
    op.execute(sa.text(
        "UPDATE plans SET catalog_items_limit = 50, channels_limit = 1 WHERE code = 'starter'"
    ))
    op.execute(sa.text(
        "UPDATE plans SET catalog_items_limit = 500, channels_limit = 5 WHERE code = 'growth'"
    ))
    op.execute(sa.text(
        "UPDATE plans SET catalog_items_limit = 5000, channels_limit = 20 WHERE code = 'scale'"
    ))
    op.execute(sa.text(
        "UPDATE plans SET catalog_items_limit = 999999, channels_limit = 999 "
        "WHERE code = 'enterprise'"
    ))


def downgrade() -> None:
    op.drop_column("plans", "channels_limit")
    op.drop_column("plans", "catalog_items_limit")
