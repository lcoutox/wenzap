"""Create agent_alerts table for error notifications

Revision ID: 062
Revises: 061
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa

revision = "062"
down_revision = "061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_alerts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=False),
        sa.Column("error_message_user", sa.Text(), nullable=False),
        sa.Column("error_message_admin", sa.Text(), nullable=False),
        sa.Column("error_details_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_alerts_workspace_id"), "agent_alerts", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_agent_alerts_agent_id"), "agent_alerts", ["agent_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_alerts_agent_id"), table_name="agent_alerts")
    op.drop_index(op.f("ix_agent_alerts_workspace_id"), table_name="agent_alerts")
    op.drop_table("agent_alerts")
