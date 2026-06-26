"""create workspace_onboarding_profiles

Revision ID: 037
Revises: 036
Create Date: 2026-06-26
"""

import sqlalchemy as sa

from alembic import op

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_onboarding_profiles",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        # Personal
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        # Intent
        sa.Column("main_objective", sa.String(100), nullable=False),
        sa.Column("expected_monthly_conversations", sa.String(50), nullable=False),
        sa.Column("ai_experience", sa.String(50), nullable=False),
        # Company
        sa.Column("company_name", sa.String(200), nullable=False),
        sa.Column("company_industry", sa.String(100), nullable=False),
        sa.Column("company_website", sa.String(500), nullable=True),
        sa.Column("role", sa.String(100), nullable=False),
        # Origin & consent
        sa.Column("heard_from", sa.String(100), nullable=False),
        sa.Column("contact_consent", sa.Boolean(), nullable=False, server_default="false"),
        # State
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_onboarding_profiles_workspace_id"),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"]
        ),
    )
    op.create_index("ix_onboarding_profiles_user_id", "workspace_onboarding_profiles", ["user_id"])
    op.create_index(
        "ix_onboarding_profiles_completed_at",
        "workspace_onboarding_profiles",
        ["completed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_onboarding_profiles_completed_at", table_name="workspace_onboarding_profiles")
    op.drop_index("ix_onboarding_profiles_user_id", table_name="workspace_onboarding_profiles")
    op.drop_table("workspace_onboarding_profiles")
