"""create catalog categories and items

Revision ID: 040
Revises: 039
Create Date: 2026-06-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── catalog_categories ────────────────────────────────────────────────────
    op.create_table(
        "catalog_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["catalog_categories.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_catalog_categories_workspace_id", "catalog_categories", ["workspace_id"]
    )
    op.create_index(
        "ix_catalog_categories_workspace_active",
        "catalog_categories",
        ["workspace_id", "is_active"],
    )

    # ── catalog_items ─────────────────────────────────────────────────────────
    op.create_table(
        "catalog_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(300), nullable=True),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("searchable_text", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(200), nullable=True),
        sa.Column("sku", sa.String(200), nullable=True),
        sa.Column("stock_quantity", sa.Integer(), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"),
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
            ["category_id"], ["catalog_categories.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'inactive', 'unavailable', 'archived')",
            name="ck_catalog_items_status",
        ),
    )
    op.create_index(
        "ix_catalog_items_workspace_id", "catalog_items", ["workspace_id"]
    )
    op.create_index(
        "ix_catalog_items_workspace_status",
        "catalog_items",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_catalog_items_category_id", "catalog_items", ["category_id"]
    )
    op.create_index(
        "ix_catalog_items_workspace_featured",
        "catalog_items",
        ["workspace_id", "is_featured"],
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_items_workspace_featured", table_name="catalog_items")
    op.drop_index("ix_catalog_items_category_id", table_name="catalog_items")
    op.drop_index("ix_catalog_items_workspace_status", table_name="catalog_items")
    op.drop_index("ix_catalog_items_workspace_id", table_name="catalog_items")
    op.drop_table("catalog_items")

    op.drop_index(
        "ix_catalog_categories_workspace_active", table_name="catalog_categories"
    )
    op.drop_index(
        "ix_catalog_categories_workspace_id", table_name="catalog_categories"
    )
    op.drop_table("catalog_categories")
