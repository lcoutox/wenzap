"""patch plans: add sources_per_kb_limit and max_source_chars

Revision ID: 020
Revises: 019
Create Date: 2026-06-23
"""

import sqlalchemy as sa

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

_PLAN_LIMITS = [
    {
        "code": "starter",
        "knowledge_bases_limit": 2,
        "sources_per_kb_limit": 20,
        "max_source_chars": 50000,
    },
    {
        "code": "growth",
        "knowledge_bases_limit": 10,
        "sources_per_kb_limit": 100,
        "max_source_chars": 100000,
    },
    {
        "code": "scale",
        "knowledge_bases_limit": 30,
        "sources_per_kb_limit": 500,
        "max_source_chars": 200000,
    },
    {
        "code": "enterprise",
        "knowledge_bases_limit": 999,
        "sources_per_kb_limit": 999,
        "max_source_chars": 500000,
    },
]


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column(
            "sources_per_kb_limit",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )
    op.add_column(
        "plans",
        sa.Column(
            "max_source_chars",
            sa.Integer(),
            nullable=False,
            server_default="50000",
        ),
    )

    for plan in _PLAN_LIMITS:
        op.execute(
            sa.text("""
                UPDATE plans
                SET
                    knowledge_bases_limit = :knowledge_bases_limit,
                    sources_per_kb_limit  = :sources_per_kb_limit,
                    max_source_chars      = :max_source_chars
                WHERE code = :code
            """).bindparams(**plan)
        )


def downgrade() -> None:
    op.drop_column("plans", "max_source_chars")
    op.drop_column("plans", "sources_per_kb_limit")
