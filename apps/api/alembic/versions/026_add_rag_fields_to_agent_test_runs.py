"""add RAG metadata fields to agent_test_runs

Revision ID: 026
Revises: 025
Create Date: 2026-06-23
"""

import sqlalchemy as sa

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("rag_used", sa.Boolean(), False),
    ("retrieval_attempted", sa.Boolean(), False),
    ("retrieved_chunks_count", sa.Integer(), None),
    ("retrieval_duration_ms", sa.Integer(), None),
    ("retrieval_score_max", sa.Float(), None),
    ("retrieval_score_min", sa.Float(), None),
    ("retrieval_error_message", sa.String(500), None),
]


def upgrade() -> None:
    for name, col_type, default in _COLUMNS:
        nullable = default is None
        kw: dict = {"nullable": nullable}
        if default is not None:
            kw["server_default"] = sa.text(str(default).lower())
        op.add_column("agent_test_runs", sa.Column(name, col_type, **kw))


def downgrade() -> None:
    for name, _, _ in reversed(_COLUMNS):
        op.drop_column("agent_test_runs", name)
