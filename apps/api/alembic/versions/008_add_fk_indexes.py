"""add foreign key indexes

Revision ID: 008
Revises: 007
Create Date: 2026-06-22
"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # workspace_members — most queried table for tenant isolation
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    # workspaces — owner lookup
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"])

    # workspace_subscriptions — plan lookup per workspace
    op.create_index("ix_workspace_subscriptions_plan_id", "workspace_subscriptions", ["plan_id"])

    # usage_counters — workspace + period range queries
    op.create_index("ix_usage_counters_workspace_id", "usage_counters", ["workspace_id"])
    op.create_index(
        "ix_usage_counters_workspace_period",
        "usage_counters",
        ["workspace_id", "period_start", "period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_counters_workspace_period", table_name="usage_counters")
    op.drop_index("ix_usage_counters_workspace_id", table_name="usage_counters")
    op.drop_index("ix_workspace_subscriptions_plan_id", table_name="workspace_subscriptions")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
