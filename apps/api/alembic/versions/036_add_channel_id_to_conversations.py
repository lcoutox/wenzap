"""add channel_id to conversations

Revision ID: 036
Revises: 035
Create Date: 2026-06-26
"""

import sqlalchemy as sa

from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("channel_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_channel_id",
        "conversations",
        "channels",
        ["channel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_conversations_channel_id", "conversations", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_channel_id", table_name="conversations")
    op.drop_constraint("fk_conversations_channel_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "channel_id")
