"""Add embedding columns to catalog_items.

Revision ID: 042
Revises: 041
Create Date: 2026-06-29

Adds pgvector embedding columns to catalog_items so that semantic
retrieval (Catálogo.4) can find catalog items by intent similarity.

Follows the same column pattern used in knowledge_chunks (migration 025).
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("catalog_items", sa.Column("embedding", Vector(1536), nullable=True))
    op.add_column(
        "catalog_items",
        sa.Column("embedding_provider", sa.String(50), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column("embedding_model", sa.String(100), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "catalog_items",
        sa.Column(
            "embedded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("catalog_items", "embedded_at")
    op.drop_column("catalog_items", "content_hash")
    op.drop_column("catalog_items", "embedding_dimension")
    op.drop_column("catalog_items", "embedding_model")
    op.drop_column("catalog_items", "embedding_provider")
    op.drop_column("catalog_items", "embedding")
