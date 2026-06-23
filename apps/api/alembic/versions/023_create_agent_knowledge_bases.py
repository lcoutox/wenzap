"""create agent_knowledge_bases

Revision ID: 023
Revises: 022
Create Date: 2026-06-23
"""

import sqlalchemy as sa

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_knowledge_bases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_base_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.UniqueConstraint("agent_id", "knowledge_base_id", name="uq_agent_knowledge_base"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_agent_kb_agent_active",
        "agent_knowledge_bases",
        ["agent_id", "is_active"],
    )
    op.create_index(
        "ix_agent_kb_knowledge_base_id",
        "agent_knowledge_bases",
        ["knowledge_base_id"],
    )
    op.create_index(
        "ix_agent_kb_workspace_id",
        "agent_knowledge_bases",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_kb_workspace_id", table_name="agent_knowledge_bases")
    op.drop_index("ix_agent_kb_knowledge_base_id", table_name="agent_knowledge_bases")
    op.drop_index("ix_agent_kb_agent_active", table_name="agent_knowledge_bases")
    op.drop_table("agent_knowledge_bases")
