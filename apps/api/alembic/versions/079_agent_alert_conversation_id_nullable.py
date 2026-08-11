"""Make agent_alerts.conversation_id nullable.

whatsapp-official-only-prd.md — most alerts are about a specific
conversation (an agent run failure), but a workspace/channel-level alert
(e.g. a WhatsApp integration getting disabled) has no single conversation
to point at.

Revision ID: 079
Revises: 078
Create Date: 2026-08-11
"""

import sqlalchemy as sa

from alembic import op

revision = "079"
down_revision = "078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "agent_alerts",
        "conversation_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "agent_alerts",
        "conversation_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
