"""Add reply_delay_seconds to agent_prompt_settings

Revision ID: 059
Revises: 058
Create Date: 2026-07-03

reply_delay_seconds: how many seconds the agent waits after the last
customer message before generating an auto-reply (debounce).

- Existing agents → 0 (preserve current immediate-reply behaviour).
- New agents are created with 5 by the application layer (agent_service).
"""

from alembic import op
import sqlalchemy as sa

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_prompt_settings",
        sa.Column(
            "reply_delay_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_prompt_settings", "reply_delay_seconds")
