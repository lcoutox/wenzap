"""Add Stripe billing integration tables and columns

Revision ID: 063
Revises: 062
Create Date: 2026-07-15
"""

from alembic import op
import sqlalchemy as sa

revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Alter workspace_subscriptions ─────────────────────────────────────
    op.add_column(
        "workspace_subscriptions",
        sa.Column("stripe_subscription_id", sa.String(100), nullable=True, unique=True),
    )
    op.add_column(
        "workspace_subscriptions",
        sa.Column("stripe_customer_id", sa.String(100), nullable=True, unique=True),
    )
    op.add_column(
        "workspace_subscriptions",
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "workspace_subscriptions",
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "workspace_subscriptions",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "workspace_subscriptions",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        op.f("ix_workspace_subscriptions_stripe_subscription_id"),
        "workspace_subscriptions",
        ["stripe_subscription_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_workspace_subscriptions_stripe_customer_id"),
        "workspace_subscriptions",
        ["stripe_customer_id"],
        unique=True,
    )

    # ── Create stripe_events table ────────────────────────────────────────
    op.create_table(
        "stripe_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stripe_event_id", sa.String(100), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stripe_events_stripe_event_id"), "stripe_events", ["stripe_event_id"], unique=True)
    op.create_index(op.f("ix_stripe_events_workspace_id"), "stripe_events", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_stripe_events_event_type"), "stripe_events", ["event_type"], unique=False)

    # ── Create stripe_sync_log table ──────────────────────────────────────
    op.create_table(
        "stripe_sync_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("stripe_response", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stripe_sync_log_workspace_id"), "stripe_sync_log", ["workspace_id"], unique=False)
    op.create_index(op.f("ix_stripe_sync_log_action"), "stripe_sync_log", ["action"], unique=False)


def downgrade() -> None:
    # Drop stripe_sync_log
    op.drop_index(op.f("ix_stripe_sync_log_action"), table_name="stripe_sync_log")
    op.drop_index(op.f("ix_stripe_sync_log_workspace_id"), table_name="stripe_sync_log")
    op.drop_table("stripe_sync_log")

    # Drop stripe_events
    op.drop_index(op.f("ix_stripe_events_event_type"), table_name="stripe_events")
    op.drop_index(op.f("ix_stripe_events_workspace_id"), table_name="stripe_events")
    op.drop_index(op.f("ix_stripe_events_stripe_event_id"), table_name="stripe_events")
    op.drop_table("stripe_events")

    # Drop workspace_subscriptions columns
    op.drop_index(op.f("ix_workspace_subscriptions_stripe_customer_id"), table_name="workspace_subscriptions")
    op.drop_index(op.f("ix_workspace_subscriptions_stripe_subscription_id"), table_name="workspace_subscriptions")
    op.drop_column("workspace_subscriptions", "cancelled_at")
    op.drop_column("workspace_subscriptions", "cancellation_reason")
    op.drop_column("workspace_subscriptions", "cancel_at_period_end")
    op.drop_column("workspace_subscriptions", "auto_renew")
    op.drop_column("workspace_subscriptions", "stripe_customer_id")
    op.drop_column("workspace_subscriptions", "stripe_subscription_id")
