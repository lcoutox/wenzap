"""Add had_tool_error to conversation_agent_runs.

execucoes-log-prd.md — conversation_agent_runs.status only reflects whether
the LLM turn itself crashed; a turn where the model replied normally but one
of its tool calls failed (e.g. Cal.com rejecting a booking) still gets
status="success". This adds an orthogonal boolean so the new "Execuções" log
screen and the Inbox error indicator can filter on real tool failures too.

Revision ID: 075
Revises: 074
Create Date: 2026-07-19
"""

import sqlalchemy as sa

from alembic import op

revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_agent_runs",
        sa.Column("had_tool_error", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("conversation_agent_runs", "had_tool_error", server_default=None)


def downgrade() -> None:
    op.drop_column("conversation_agent_runs", "had_tool_error")
