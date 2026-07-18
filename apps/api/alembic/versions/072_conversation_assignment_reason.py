"""Add assignment_reason to conversations.

agent-tools-batch-2-prd.md — captures the model-supplied reason when the
"assign_operator" tool sets assigned_user_id. Deliberately a separate column
from handoff_reason (request_human's) — the Inbox only ever renders
handoff_reason while assigned_user_id is still null (the "Solicitar humano"
limbo state), so reusing it here would silently never display. Cleared by
return_to_ai(), same as handoff_reason.

Revision ID: 072
Revises: 071
Create Date: 2026-07-18
"""

import sqlalchemy as sa

from alembic import op

revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("assignment_reason", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "assignment_reason")
