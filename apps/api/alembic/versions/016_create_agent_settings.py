"""create agent_prompt_settings and agent_model_settings with backfill

Revision ID: 016
Revises: 015
Create Date: 2026-06-22

Splits agent configuration into two satellite tables (1:1 with agents):

  agent_prompt_settings  — system_prompt, persona, response_style, language_mode
  agent_model_settings   — ai_model_id (NOT NULL), model_name, temperature, context params

Fields are backfilled from agents.* immediately after table creation.
Old columns in agents are NOT removed in this migration (Phase 2.4 policy).
Removal is deferred to a future phase once service layer is fully stable.
"""

import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_prompt_settings ─────────────────────────────────────────────────

    op.create_table(
        "agent_prompt_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("persona", sa.Text(), nullable=True),
        sa.Column("response_style", sa.String(50), nullable=True),
        sa.Column("language_mode", sa.String(20), nullable=True),
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
        sa.UniqueConstraint("agent_id", name="uq_agent_prompt_settings_agent_id"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_agent_prompt_settings_agent_id",
        "agent_prompt_settings",
        ["agent_id"],
    )

    # ── agent_model_settings ──────────────────────────────────────────────────

    op.create_table(
        "agent_model_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("ai_model_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("temperature", sa.Numeric(3, 2), nullable=False, server_default="0.70"),
        sa.Column("context_window_tier", sa.String(20), nullable=True),
        sa.Column("context_window_tokens", sa.Integer(), nullable=True),
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
        sa.UniqueConstraint("agent_id", name="uq_agent_model_settings_agent_id"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], ondelete="CASCADE"
        ),
        # RESTRICT: catalog models must be deactivated (is_active=False), never deleted.
        sa.ForeignKeyConstraint(
            ["ai_model_id"], ["ai_models.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_agent_model_settings_agent_id",
        "agent_model_settings",
        ["agent_id"],
    )
    op.create_index(
        "ix_agent_model_settings_ai_model_id",
        "agent_model_settings",
        ["ai_model_id"],
    )

    # ── Backfill from agents ──────────────────────────────────────────────────

    op.execute(sa.text("""
        INSERT INTO agent_prompt_settings (id, agent_id, system_prompt, persona)
        SELECT gen_random_uuid(), id, system_prompt, persona
        FROM agents
    """))

    op.execute(sa.text("""
        INSERT INTO agent_model_settings (id, agent_id, ai_model_id, model_name, temperature)
        SELECT gen_random_uuid(), id, ai_model_id, model_name, temperature
        FROM agents
        WHERE ai_model_id IS NOT NULL
    """))


def downgrade() -> None:
    op.drop_index("ix_agent_model_settings_ai_model_id", "agent_model_settings")
    op.drop_index("ix_agent_model_settings_agent_id", "agent_model_settings")
    op.drop_table("agent_model_settings")
    op.drop_index("ix_agent_prompt_settings_agent_id", "agent_prompt_settings")
    op.drop_table("agent_prompt_settings")
