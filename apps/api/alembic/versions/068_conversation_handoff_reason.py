"""Add handoff_reason to conversations.

request-human-tool-prd.md — captures the model-supplied `reason` when the
"request_human" tool pauses the AI on a conversation, so the Inbox can show
why without the operator re-reading the whole thread. NULL for every other
path that disables ai_enabled (e.g. a human manually clicking "Assumir"),
and cleared again by return_to_ai() once the conversation goes back to the AI.

Revision ID: 068
Revises: 067
Create Date: 2026-07-17
"""

import sqlalchemy as sa

from alembic import op

revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("handoff_reason", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "handoff_reason")
