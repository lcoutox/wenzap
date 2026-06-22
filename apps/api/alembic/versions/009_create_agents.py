"""create agents

Revision ID: 009
Revises: 008
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("persona", sa.Text(), nullable=True),
        sa.Column("model_provider", sa.String(50), nullable=False, server_default="anthropic"),
        sa.Column("model_name", sa.String(100), nullable=False, server_default="claude-sonnet-4-6"),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=False, server_default="0.70"),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )

    # Tenant isolation — most frequent filter
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])

    # Status filter within a workspace (listagem com filtro por status)
    op.create_index("ix_agents_workspace_status", "agents", ["workspace_id", "status"])

    # Traceability — who created
    op.create_index("ix_agents_created_by_user_id", "agents", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_created_by_user_id", table_name="agents")
    op.drop_index("ix_agents_workspace_status", table_name="agents")
    op.drop_index("ix_agents_workspace_id", table_name="agents")
    op.drop_table("agents")
