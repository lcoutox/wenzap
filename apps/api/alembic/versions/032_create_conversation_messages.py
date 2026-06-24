"""create conversation_messages table

Revision ID: 032
Revises: 031
Create Date: 2026-06-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("sender_type", sa.String(16), nullable=False),
        sa.Column("sender_user_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False, server_default="text"),
        sa.Column("external_message_id", sa.String(300), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # No updated_at — messages are immutable by design.
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound', 'internal')",
            name="ck_conv_messages_direction",
        ),
        sa.CheckConstraint(
            "sender_type IN ('customer', 'human', 'agent', 'system')",
            name="ck_conv_messages_sender_type",
        ),
        # content_type left open (no check constraint) to allow future types
        # (image, file, audio, system_event) without a migration.
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conv_messages_conversation_id", "conversation_messages", ["conversation_id"]
    )
    op.create_index(
        "ix_conv_messages_workspace_id", "conversation_messages", ["workspace_id"]
    )
    op.create_index(
        "ix_conv_messages_conversation_created_at",
        "conversation_messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conv_messages_conversation_created_at", table_name="conversation_messages"
    )
    op.drop_index("ix_conv_messages_workspace_id", table_name="conversation_messages")
    op.drop_index("ix_conv_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
