"""enable pgvector extension

Revision ID: 024
Revises: 023
Create Date: 2026-06-23
"""

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fails clearly if the pgvector extension is not installed on the server.
    # Use pgvector/pgvector:pg16 (or equivalent) Docker image in all environments.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
