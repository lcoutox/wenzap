"""create agent_catalog_categories table

Revision ID: 044
Revises: 043
Create Date: 2026-06-29

"""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_catalog_categories",
        sa.Column("id", sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["catalog_categories.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_id", "category_id", name="uq_agent_catalog_category"),
    )
    op.create_index("ix_agent_catalog_categories_agent_id", "agent_catalog_categories", ["agent_id"])
    op.create_index("ix_agent_catalog_categories_workspace_id", "agent_catalog_categories", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_catalog_categories_workspace_id", "agent_catalog_categories")
    op.drop_index("ix_agent_catalog_categories_agent_id", "agent_catalog_categories")
    op.drop_table("agent_catalog_categories")
