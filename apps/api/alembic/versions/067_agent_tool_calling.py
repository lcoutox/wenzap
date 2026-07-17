"""Create agent_tools and agent_tool_calls tables.

Tool-calling infra PRD, Fase 3 — agent_tools is the 1:N satellite of agents
holding each tool an agent can call (per docs/architecture/AGENT_MODULE_ARCHITECTURE.md's
own proposed shape, extended with name/description since real tool-calling
needs a model-facing identifier and a short action-oriented description).
agent_tool_calls audits every LLM round-trip within a tool-calling loop,
attached to either a conversation_agent_run (production replies) or an
agent_test_run (Playground) — never both.

Revision ID: 067
Revises: 066
Create Date: 2026-07-17
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tools",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("tool_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id", "name", name="uq_agent_tool_name"),
    )
    op.create_index("ix_agent_tools_agent_id", "agent_tools", ["agent_id"])
    op.create_index("ix_agent_tools_workspace_id", "agent_tools", ["workspace_id"])

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("conversation_agent_run_id", sa.UUID(), nullable=True),
        sa.Column("agent_test_run_id", sa.UUID(), nullable=True),
        sa.Column("call_index", sa.Integer(), nullable=False),
        sa.Column("stop_reason", sa.String(32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("tool_calls", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_agent_run_id"], ["conversation_agent_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["agent_test_run_id"], ["agent_test_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_tool_calls_conversation_agent_run_id",
        "agent_tool_calls",
        ["conversation_agent_run_id"],
    )
    op.create_index(
        "ix_agent_tool_calls_agent_test_run_id",
        "agent_tool_calls",
        ["agent_test_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_tool_calls_agent_test_run_id", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_conversation_agent_run_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")

    op.drop_index("ix_agent_tools_workspace_id", table_name="agent_tools")
    op.drop_index("ix_agent_tools_agent_id", table_name="agent_tools")
    op.drop_table("agent_tools")
