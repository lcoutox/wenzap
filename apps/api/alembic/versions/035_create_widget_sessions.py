"""create widget_sessions table

Revision ID: 035
Revises: 034
Create Date: 2026-06-24
"""

import sqlalchemy as sa

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "widget_sessions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("session_token", sa.String(200), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_token", name="uq_widget_sessions_session_token"),
    )

    op.create_index("ix_widget_sessions_channel_id", "widget_sessions", ["channel_id"])
    op.create_index("ix_widget_sessions_workspace_id", "widget_sessions", ["workspace_id"])
    op.create_index("ix_widget_sessions_session_token", "widget_sessions", ["session_token"])
    op.create_index(
        "ix_widget_sessions_channel_token",
        "widget_sessions",
        ["channel_id", "session_token"],
    )


def downgrade() -> None:
    op.drop_index("ix_widget_sessions_channel_token", table_name="widget_sessions")
    op.drop_index("ix_widget_sessions_session_token", table_name="widget_sessions")
    op.drop_index("ix_widget_sessions_workspace_id", table_name="widget_sessions")
    op.drop_index("ix_widget_sessions_channel_id", table_name="widget_sessions")
    op.drop_table("widget_sessions")
