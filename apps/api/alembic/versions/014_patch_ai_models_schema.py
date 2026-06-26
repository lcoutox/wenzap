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
    # Rename name → display_name only if the old column name still exists.
    # When migration 010 already creates the column as display_name, this is a no-op.
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='ai_models' AND column_name='name'
            ) THEN
                ALTER TABLE ai_models RENAME COLUMN name TO display_name;
            END IF;
        END $$;
    """))

    # Extend model_name to 200 chars (safe re-run).
    op.execute(sa.text("ALTER TABLE ai_models ALTER COLUMN model_name TYPE VARCHAR(200)"))

    # Add columns if they don't already exist (migration 010 may have created them).
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS credits_per_message INTEGER NOT NULL DEFAULT 1"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS min_plan_code VARCHAR(50) NOT NULL DEFAULT 'starter'"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS context_window_tokens INTEGER"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS is_recommended BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS supports_vision BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS supports_tools BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS supports_reasoning BOOLEAN NOT NULL DEFAULT false"
    ))
    op.execute(sa.text(
        "ALTER TABLE ai_models ADD COLUMN IF NOT EXISTS supports_code BOOLEAN NOT NULL DEFAULT false"
    ))

    # Create index if it doesn't already exist.
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ai_models_min_plan_code ON ai_models (min_plan_code)"
    ))

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
