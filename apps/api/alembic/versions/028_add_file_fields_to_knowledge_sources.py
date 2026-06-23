"""add file fields to knowledge_sources

Revision ID: 028
Revises: 027
Create Date: 2026-06-23
"""

import sqlalchemy as sa

from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("original_filename", sa.Text(), nullable=True))
    op.add_column("knowledge_sources", sa.Column("mime_type", sa.String(128), nullable=True))
    op.add_column("knowledge_sources", sa.Column("file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("knowledge_sources", sa.Column("storage_provider", sa.String(32), nullable=True))
    op.add_column("knowledge_sources", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("knowledge_sources", sa.Column("content_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_sources", "content_hash")
    op.drop_column("knowledge_sources", "storage_key")
    op.drop_column("knowledge_sources", "storage_provider")
    op.drop_column("knowledge_sources", "file_size_bytes")
    op.drop_column("knowledge_sources", "mime_type")
    op.drop_column("knowledge_sources", "original_filename")
