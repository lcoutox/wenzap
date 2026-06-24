"""create conversation_agent_runs table

Revision ID: 033
Revises: 032
Create Date: 2026-06-24
"""

import sqlalchemy as sa

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_agent_runs",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("trigger_message_id", sa.UUID(), nullable=False),
        sa.Column("response_message_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("ai_model_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("rag_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("retrieved_chunks_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retrieval_duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["trigger_message_id"], ["conversation_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["response_message_id"], ["conversation_messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ai_model_id"], ["ai_models.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'skipped', 'blocked')",
            name="ck_conv_agent_runs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conv_agent_runs_workspace_conversation",
        "conversation_agent_runs",
        ["workspace_id", "conversation_id"],
    )
    op.create_index(
        "ix_conv_agent_runs_trigger_message_id",
        "conversation_agent_runs",
        ["trigger_message_id"],
    )
    op.create_index(
        "ix_conv_agent_runs_response_message_id",
        "conversation_agent_runs",
        ["response_message_id"],
    )
    op.create_index(
        "ix_conv_agent_runs_agent_id",
        "conversation_agent_runs",
        ["agent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_conv_agent_runs_agent_id", table_name="conversation_agent_runs")
    op.drop_index("ix_conv_agent_runs_response_message_id", table_name="conversation_agent_runs")
    op.drop_index("ix_conv_agent_runs_trigger_message_id", table_name="conversation_agent_runs")
    op.drop_index(
        "ix_conv_agent_runs_workspace_conversation", table_name="conversation_agent_runs"
    )
    op.drop_table("conversation_agent_runs")
