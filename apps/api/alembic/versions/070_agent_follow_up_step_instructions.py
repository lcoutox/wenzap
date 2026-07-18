"""Add custom_instructions to agent_follow_up_steps.

follow-up-tool-prd.md adendo — optional per-step instruction, combined with
(not replacing) AgentFollowUpSettings.custom_instructions (the general one
that applies to every step). NULL means the step just relies on the general
instruction plus the step-number/hours-elapsed context already in the prompt.

Revision ID: 070
Revises: 069
Create Date: 2026-07-18
"""

import sqlalchemy as sa

from alembic import op

revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_follow_up_steps",
        sa.Column("custom_instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_follow_up_steps", "custom_instructions")
