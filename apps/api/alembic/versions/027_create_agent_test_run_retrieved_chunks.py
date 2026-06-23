"""create agent_test_run_retrieved_chunks

Revision ID: 027
Revises: 026
Create Date: 2026-06-23
"""

import sqlalchemy as sa

from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_test_run_retrieved_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_test_run_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_chunk_id", sa.UUID(), nullable=True),
        sa.Column("knowledge_base_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "injected_into_prompt",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["agent_test_run_id"],
            ["agent_test_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_chunk_id"],
            ["knowledge_chunks.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_agent_test_run_retrieved_chunks_run_id",
        "agent_test_run_retrieved_chunks",
        ["agent_test_run_id"],
    )
    op.create_index(
        "ix_agent_test_run_retrieved_chunks_chunk_id",
        "agent_test_run_retrieved_chunks",
        ["knowledge_chunk_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_test_run_retrieved_chunks_chunk_id",
        table_name="agent_test_run_retrieved_chunks",
    )
    op.drop_index(
        "ix_agent_test_run_retrieved_chunks_run_id",
        table_name="agent_test_run_retrieved_chunks",
    )
    op.drop_table("agent_test_run_retrieved_chunks")
