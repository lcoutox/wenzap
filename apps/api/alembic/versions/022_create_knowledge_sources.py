"""create knowledge_sources

Revision ID: 022
Revises: 021
Create Date: 2026-06-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("knowledge_base_id", sa.UUID(), nullable=False),
        # manual_text | faq_qa  (4.1 scope)
        # txt | markdown | pdf_simple | csv_simple added in Phase 4.4
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        # raw content (manual_text / faq_qa); NULL for file-based sources (Phase 4.4)
        sa.Column("content_text", sa.Text(), nullable=True),
        # pending | ready | failed | archived
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        # stores source_category and, for faq_qa, the original qa_pairs list
        sa.Column("metadata_json", JSONB(), nullable=True),
        # sanitised error from processing (no stacktrace, no secrets)
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index(
        "ix_knowledge_sources_kb_id",
        "knowledge_sources",
        ["knowledge_base_id"],
    )
    op.create_index(
        "ix_knowledge_sources_workspace_status",
        "knowledge_sources",
        ["workspace_id", "status"],
    )
    op.create_index(
        "ix_knowledge_sources_kb_status",
        "knowledge_sources",
        ["knowledge_base_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_sources_kb_status", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_workspace_status", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_kb_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
