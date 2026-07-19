"""Add full-text search and HNSW indexes to catalog_items.

catalog-retrieval-robustness-prd.md — two index-only additions, no schema or
data changes:
- GIN expression index over to_tsvector('portuguese', searchable_text), so
  the new native full-text search (replacing ILIKE term-counting) can use a
  real index instead of a sequential scan.
- HNSW index on the pgvector embedding column (vector_cosine_ops) — semantic
  search had no ANN index at all before this (sequential scan every time).

Revision ID: 074
Revises: 073
Create Date: 2026-07-19
"""

from alembic import op

revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_catalog_items_fts ON catalog_items "
        "USING gin (to_tsvector('portuguese', coalesce(searchable_text, '')))"
    )
    op.execute(
        "CREATE INDEX ix_catalog_items_embedding_hnsw ON catalog_items "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_catalog_items_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_catalog_items_fts")
