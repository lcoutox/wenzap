"""Add resolution_summary to conversations.

mark-resolved-tool-prd.md — captures the model-supplied summary when the
"mark_resolved" tool sets status="resolved", so the Inbox can show why
without the operator re-reading the whole thread (same pattern as
handoff_reason for the "request_human" tool). Cleared whenever status moves
away from "resolved" (auto-reopen on new customer message, or a manual
status change).

Revision ID: 071
Revises: 070
Create Date: 2026-07-18
"""

import sqlalchemy as sa

from alembic import op

revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("resolution_summary", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "resolution_summary")
