"""add max_file_size_bytes to plans

Revision ID: 029
Revises: 028
Create Date: 2026-06-23
"""

import sqlalchemy as sa

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None

# File size limits per plan (bytes)
_PLAN_LIMITS = {
    "starter":    2_097_152,   # 2 MB
    "growth":    10_485_760,   # 10 MB
    "scale":     26_214_400,   # 25 MB
    "enterprise": 52_428_800,  # 50 MB
}


def upgrade() -> None:
    op.add_column("plans", sa.Column("max_file_size_bytes", sa.BigInteger(), nullable=True))

    plans_table = sa.table(
        "plans",
        sa.column("code", sa.String),
        sa.column("max_file_size_bytes", sa.BigInteger),
    )
    for code, limit in _PLAN_LIMITS.items():
        op.execute(
            plans_table.update()
            .where(plans_table.c.code == code)
            .values(max_file_size_bytes=limit)
        )


def downgrade() -> None:
    op.drop_column("plans", "max_file_size_bytes")
