"""Pipeline foundation — pipelines, pipeline_stages, pipeline_entries.

Revision ID: 055
Revises: 054
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pipelines ─────────────────────────────────────────────────────────────
    op.create_table(
        "pipelines",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "show_inactive_conversations",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipelines_workspace_id", "pipelines", ["workspace_id"])

    # ── pipeline_stages ───────────────────────────────────────────────────────
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("pipeline_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("assigned_agent_id", sa.UUID(), nullable=True),
        sa.Column("entry_condition", sa.Text(), nullable=True),
        sa.Column("extra_prompt", sa.Text(), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "is_removal_stage", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "request_contact_info",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "stay_limit_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("stay_limit_minutes", sa.Integer(), nullable=True),
        sa.Column("webhook_url", sa.String(1000), nullable=True),
        sa.Column("webhook_auth_header", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_stages_pipeline_id", "pipeline_stages", ["pipeline_id"])
    op.create_index("ix_pipeline_stages_workspace_id", "pipeline_stages", ["workspace_id"])

    # ── pipeline_entries ──────────────────────────────────────────────────────
    op.create_table(
        "pipeline_entries",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("pipeline_id", sa.UUID(), nullable=True),
        sa.Column("stage_id", sa.UUID(), nullable=True),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("assigned_agent_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("entered_stage_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["stage_id"], ["pipeline_stages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'removed')", name="ck_pipeline_entries_status"),
        sa.UniqueConstraint("pipeline_id", "conversation_id", name="uq_pipeline_entries_pipeline_conversation"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_entries_pipeline_id", "pipeline_entries", ["pipeline_id"])
    op.create_index("ix_pipeline_entries_workspace_id", "pipeline_entries", ["workspace_id"])
    op.create_index("ix_pipeline_entries_conversation_id", "pipeline_entries", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_entries_conversation_id", table_name="pipeline_entries")
    op.drop_index("ix_pipeline_entries_workspace_id", table_name="pipeline_entries")
    op.drop_index("ix_pipeline_entries_pipeline_id", table_name="pipeline_entries")
    op.drop_table("pipeline_entries")

    op.drop_index("ix_pipeline_stages_workspace_id", table_name="pipeline_stages")
    op.drop_index("ix_pipeline_stages_pipeline_id", table_name="pipeline_stages")
    op.drop_table("pipeline_stages")

    op.drop_index("ix_pipelines_workspace_id", table_name="pipelines")
    op.drop_table("pipelines")
