"""Add conversation follow-up: last_customer_message_at + follow-up tables.

follow-up-tool-prd.md — third tool off the "Em breve" list in the Ferramentas
tab, but architecturally distinct from the tool-calling ones (HTTP Tool,
Solicitar Humano): a background sweep decides to start a turn after silence,
not the model deciding mid-turn. `conversations.last_customer_message_at` is
the silence anchor (NULL for pre-existing conversations, no backfill — first
follow-up eligibility starts from their next real customer message).
`agent_follow_up_settings`/`agent_follow_up_steps` are the 1:1/1:N config
satellites; `conversation_follow_ups` is both the audit trail and the
concurrency guard (unique constraint on conversation_id+step_order+
silence_anchor — see the model docstring for why).

Revision ID: 069
Revises: 068
Create Date: 2026-07-18
"""

import sqlalchemy as sa

from alembic import op

revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("last_customer_message_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "agent_follow_up_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", name="uq_agent_follow_up_settings_agent_id"),
    )
    op.create_index(
        "ix_agent_follow_up_settings_workspace_id", "agent_follow_up_settings", ["workspace_id"]
    )

    op.create_table(
        "agent_follow_up_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("delay_hours", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "step_order", name="uq_agent_follow_up_step_order"),
    )
    op.create_index("ix_agent_follow_up_steps_agent_id", "agent_follow_up_steps", ["agent_id"])

    op.create_table(
        "conversation_follow_ups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("silence_anchor", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conversation_message_id", sa.UUID(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_message_id"], ["conversation_messages.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id", "step_order", "silence_anchor",
            name="uq_conversation_follow_up_step_per_silence_period",
        ),
    )
    op.create_index(
        "ix_conversation_follow_ups_conversation_id",
        "conversation_follow_ups",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_follow_ups_conversation_id", table_name="conversation_follow_ups"
    )
    op.drop_table("conversation_follow_ups")

    op.drop_index("ix_agent_follow_up_steps_agent_id", table_name="agent_follow_up_steps")
    op.drop_table("agent_follow_up_steps")

    op.drop_index(
        "ix_agent_follow_up_settings_workspace_id", table_name="agent_follow_up_settings"
    )
    op.drop_table("agent_follow_up_settings")

    op.drop_column("conversations", "last_customer_message_at")
