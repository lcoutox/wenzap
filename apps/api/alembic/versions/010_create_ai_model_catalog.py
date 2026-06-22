"""create ai model catalog

Revision ID: 010
Revises: 009
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_model_providers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "ai_models",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("credits_per_message", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_plan_code", sa.String(50), nullable=False, server_default="starter"),
        sa.Column("context_window_tokens", sa.Integer(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_recommended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("supports_vision", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_tools", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_reasoning", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supports_code", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.ForeignKeyConstraint(["provider_id"], ["ai_model_providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])
    op.create_index("ix_ai_models_is_active", "ai_models", ["is_active"])
    op.create_index("ix_ai_models_min_plan_code", "ai_models", ["min_plan_code"])


def downgrade() -> None:
    op.drop_index("ix_ai_models_min_plan_code", table_name="ai_models")
    op.drop_index("ix_ai_models_is_active", table_name="ai_models")
    op.drop_index("ix_ai_models_provider_id", table_name="ai_models")
    op.drop_table("ai_models")
    op.drop_table("ai_model_providers")
