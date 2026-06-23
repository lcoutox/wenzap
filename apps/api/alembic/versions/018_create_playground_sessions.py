"""create agent_playground_sessions

Revision ID: 018
Revises: 017
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_playground_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column(
            "title",
            sa.String(200),
            nullable=False,
            server_default="Nova conversa",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL"
        ),
    )

    op.create_index(
        "ix_playground_sessions_workspace_id",
        "agent_playground_sessions",
        ["workspace_id"],
    )
    op.create_index(
        "ix_playground_sessions_agent_id",
        "agent_playground_sessions",
        ["agent_id"],
    )
    op.create_index(
        "ix_playground_sessions_created_at",
        "agent_playground_sessions",
        [sa.text("created_at DESC")],
    )
    # Composite index optimised for the sessions list query:
    # WHERE workspace_id = ? AND agent_id = ? ORDER BY updated_at DESC
    op.create_index(
        "ix_playground_sessions_workspace_agent_updated",
        "agent_playground_sessions",
        ["workspace_id", "agent_id", sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_playground_sessions_workspace_agent_updated",
        table_name="agent_playground_sessions",
    )
    op.drop_index(
        "ix_playground_sessions_created_at",
        table_name="agent_playground_sessions",
    )
    op.drop_index(
        "ix_playground_sessions_agent_id",
        table_name="agent_playground_sessions",
    )
    op.drop_index(
        "ix_playground_sessions_workspace_id",
        table_name="agent_playground_sessions",
    )
    op.drop_table("agent_playground_sessions")
