"""create agent_test_runs table

Revision ID: 017
Revises: 016
Create Date: 2026-06-22

Records executions that reached the LLM provider (success or provider error).
Executions blocked BEFORE the LLM call (insufficient credits, unsupported model,
wrong agent status, plan limit) are NOT recorded — only provider interactions are logged.

Columns:
  status: "success" | "error"
  error_message: sanitized provider error (no stacktrace, no API keys, no prompt content)

See app/models/agent_test_run.py for the full design rationale.
"""

import sqlalchemy as sa

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_test_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("ai_model_id", sa.UUID(), nullable=True),
        sa.Column("provider_code", sa.String(50), nullable=False),
        sa.Column("model_code", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("credits_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"],     ["agents.id"],     ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"],       ["users.id"],      ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ai_model_id"],   ["ai_models.id"],  ondelete="SET NULL"),
    )
    op.create_index("ix_agent_test_runs_workspace_id", "agent_test_runs", ["workspace_id"])
    op.create_index("ix_agent_test_runs_agent_id",     "agent_test_runs", ["agent_id"])
    op.create_index(
        "ix_agent_test_runs_created_at",
        "agent_test_runs",
        ["created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("ix_agent_test_runs_created_at", "agent_test_runs")
    op.drop_index("ix_agent_test_runs_agent_id",   "agent_test_runs")
    op.drop_index("ix_agent_test_runs_workspace_id","agent_test_runs")
    op.drop_table("agent_test_runs")
