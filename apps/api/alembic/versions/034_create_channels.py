"""create channels table

Revision ID: 034
Revises: 033
Create Date: 2026-06-24
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("channel_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("public_key", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("config_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "allowed_origins",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "channel_type IN ('web_widget', 'whatsapp', 'instagram', 'email', 'api')",
            name="ck_channels_channel_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'archived')",
            name="ck_channels_status",
        ),
    )

    op.create_index("ix_channels_public_key", "channels", ["public_key"], unique=True)
    op.create_index("ix_channels_workspace_id", "channels", ["workspace_id"])
    op.create_index("ix_channels_agent_id", "channels", ["agent_id"])
    op.create_index(
        "ix_channels_workspace_type", "channels", ["workspace_id", "channel_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_channels_workspace_type", table_name="channels")
    op.drop_index("ix_channels_agent_id", table_name="channels")
    op.drop_index("ix_channels_workspace_id", table_name="channels")
    op.drop_index("ix_channels_public_key", table_name="channels")
    op.drop_table("channels")
