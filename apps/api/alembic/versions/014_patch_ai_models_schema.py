"""patch ai_models schema to match current model definition

Revision ID: 014
Revises: 013
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename name → display_name
    op.alter_column("ai_models", "name", new_column_name="display_name")

    # Extend model_name to 200 chars (may already be 200 via 012, safe to re-run)
    op.alter_column("ai_models", "model_name", type_=sa.String(200))

    # Add missing columns
    op.add_column("ai_models", sa.Column(
        "credits_per_message", sa.Integer(), nullable=False, server_default="1"
    ))
    op.add_column("ai_models", sa.Column(
        "min_plan_code", sa.String(50), nullable=False, server_default="starter"
    ))
    op.add_column("ai_models", sa.Column(
        "context_window_tokens", sa.Integer(), nullable=True
    ))
    op.add_column("ai_models", sa.Column(
        "is_recommended", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("ai_models", sa.Column(
        "is_featured", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("ai_models", sa.Column(
        "supports_vision", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("ai_models", sa.Column(
        "supports_tools", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("ai_models", sa.Column(
        "supports_reasoning", sa.Boolean(), nullable=False, server_default="false"
    ))
    op.add_column("ai_models", sa.Column(
        "supports_code", sa.Boolean(), nullable=False, server_default="false"
    ))

    # Add missing index
    op.create_index("ix_ai_models_min_plan_code", "ai_models", ["min_plan_code"])

    # Re-seed models with correct values (UPDATE existing rows seeded by 011)
    op.execute(sa.text("""
        UPDATE ai_models SET
            credits_per_message = CASE code
                WHEN 'nexbrain-lite'  THEN 1
                WHEN 'nexbrain-prime' THEN 2
                WHEN 'nexbrain-ultra' THEN 8
                WHEN 'claude-haiku'   THEN 1
                WHEN 'claude-sonnet'  THEN 3
                WHEN 'claude-opus'    THEN 10
                WHEN 'gpt-mini'       THEN 1
                WHEN 'gpt-advanced'   THEN 5
                WHEN 'gemini-flash'   THEN 1
                WHEN 'gemini-pro'     THEN 4
                ELSE 1
            END,
            min_plan_code = CASE code
                WHEN 'nexbrain-ultra' THEN 'growth'
                WHEN 'claude-sonnet'  THEN 'growth'
                WHEN 'claude-opus'    THEN 'scale'
                WHEN 'gpt-advanced'   THEN 'growth'
                WHEN 'gemini-pro'     THEN 'growth'
                ELSE 'starter'
            END,
            context_window_tokens = CASE code
                WHEN 'nexbrain-lite'  THEN 32000
                WHEN 'nexbrain-prime' THEN 128000
                WHEN 'nexbrain-ultra' THEN 200000
                WHEN 'claude-haiku'   THEN 200000
                WHEN 'claude-sonnet'  THEN 200000
                WHEN 'claude-opus'    THEN 200000
                WHEN 'gpt-mini'       THEN 128000
                WHEN 'gpt-advanced'   THEN 128000
                WHEN 'gemini-flash'   THEN 1000000
                WHEN 'gemini-pro'     THEN 1000000
                ELSE NULL
            END,
            is_recommended = CASE code WHEN 'nexbrain-prime' THEN true ELSE false END,
            is_featured    = CASE code
                WHEN 'nexbrain-prime' THEN true
                WHEN 'nexbrain-ultra' THEN true
                ELSE false
            END,
            supports_vision    = CASE code
                WHEN 'nexbrain-ultra' THEN true
                WHEN 'claude-opus'    THEN true
                WHEN 'gpt-mini'       THEN true
                WHEN 'gpt-advanced'   THEN true
                WHEN 'gemini-flash'   THEN true
                WHEN 'gemini-pro'     THEN true
                ELSE false
            END,
            supports_tools = CASE code
                WHEN 'nexbrain-lite' THEN true
                WHEN 'nexbrain-prime' THEN true
                WHEN 'nexbrain-ultra' THEN true
                WHEN 'claude-haiku'  THEN true
                WHEN 'claude-sonnet' THEN true
                WHEN 'claude-opus'   THEN true
                WHEN 'gpt-mini'      THEN true
                WHEN 'gpt-advanced'  THEN true
                WHEN 'gemini-flash'  THEN true
                WHEN 'gemini-pro'    THEN true
                ELSE false
            END,
            supports_reasoning = CASE code
                WHEN 'nexbrain-prime' THEN true
                WHEN 'nexbrain-ultra' THEN true
                WHEN 'claude-sonnet'  THEN true
                WHEN 'claude-opus'    THEN true
                WHEN 'gpt-advanced'   THEN true
                WHEN 'gemini-pro'     THEN true
                ELSE false
            END,
            supports_code = CASE code
                WHEN 'nexbrain-lite'  THEN true
                WHEN 'nexbrain-prime' THEN true
                WHEN 'nexbrain-ultra' THEN true
                WHEN 'claude-haiku'   THEN true
                WHEN 'claude-sonnet'  THEN true
                WHEN 'claude-opus'    THEN true
                WHEN 'gpt-mini'       THEN true
                WHEN 'gpt-advanced'   THEN true
                WHEN 'gemini-flash'   THEN true
                WHEN 'gemini-pro'     THEN true
                ELSE false
            END
    """))


def downgrade() -> None:
    op.drop_index("ix_ai_models_min_plan_code", "ai_models")
    op.drop_column("ai_models", "supports_code")
    op.drop_column("ai_models", "supports_reasoning")
    op.drop_column("ai_models", "supports_tools")
    op.drop_column("ai_models", "supports_vision")
    op.drop_column("ai_models", "is_featured")
    op.drop_column("ai_models", "is_recommended")
    op.drop_column("ai_models", "context_window_tokens")
    op.drop_column("ai_models", "min_plan_code")
    op.drop_column("ai_models", "credits_per_message")
    op.alter_column("ai_models", "display_name", new_column_name="name")
