"""create agent_playground_messages

Revision ID: 019
Revises: 018
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_playground_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        # 'user' | 'assistant'
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # NULL for user messages; points to the run that produced the response.
        sa.Column("agent_test_run_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["agent_playground_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_test_run_id"],
            ["agent_test_runs.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_playground_messages_session_id",
        "agent_playground_messages",
        ["session_id"],
    )
    # Optimised for fetching a session's messages in chronological order.
    op.create_index(
        "ix_playground_messages_session_created",
        "agent_playground_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_playground_messages_session_created",
        table_name="agent_playground_messages",
    )
    op.drop_index(
        "ix_playground_messages_session_id",
        table_name="agent_playground_messages",
    )
    op.drop_table("agent_playground_messages")
