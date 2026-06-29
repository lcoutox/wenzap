"""create catalog_media table

Revision ID: 041
Revises: 040
Create Date: 2026-06-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("alt_text", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["catalog_items.id"], ondelete="CASCADE"),
    )

    op.create_index("ix_catalog_media_item_id", "catalog_media", ["item_id"])
    op.create_index("ix_catalog_media_workspace_id", "catalog_media", ["workspace_id"])
    op.create_index(
        "ix_catalog_media_item_primary",
        "catalog_media",
        ["item_id", "is_primary"],
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_media_item_primary", table_name="catalog_media")
    op.drop_index("ix_catalog_media_workspace_id", table_name="catalog_media")
    op.drop_index("ix_catalog_media_item_id", table_name="catalog_media")
    op.drop_table("catalog_media")
