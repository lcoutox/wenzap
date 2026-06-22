"""update agents: add ai_model_id, drop model_provider, backfill

Revision ID: 012
Revises: 011
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

# UUID of nexbrain-prime — the default fallback model
_DEFAULT_MODEL_CODE = "nexbrain-prime"


def upgrade() -> None:
    # 1. Add ai_model_id (nullable FK to ai_models)
    op.add_column(
        "agents",
        sa.Column("ai_model_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_agents_ai_model_id",
        "agents",
        "ai_models",
        ["ai_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_agents_ai_model_id", "agents", ["ai_model_id"])

    # 2. Backfill: match existing agents by model_name to ai_models.model_name
    op.execute(sa.text("""
        UPDATE agents a
        SET ai_model_id = m.id
        FROM ai_models m
        WHERE a.model_name = m.model_name
          AND a.ai_model_id IS NULL
    """))

    # 3. For agents that still have no match, assign the default model
    _c = _DEFAULT_MODEL_CODE
    op.execute(sa.text(
        f"UPDATE agents "
        f"SET ai_model_id = (SELECT id FROM ai_models WHERE code = '{_c}' LIMIT 1),"
        f"    model_name  = (SELECT model_name FROM ai_models WHERE code = '{_c}' LIMIT 1)"
        f" WHERE ai_model_id IS NULL"
    ))

    # 4. Extend model_name column to match new schema (200 chars)
    op.alter_column("agents", "model_name", type_=sa.String(200), existing_nullable=False)

    # 5. Drop model_provider column
    op.drop_column("agents", "model_provider")


def downgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "model_provider",
            sa.String(50),
            nullable=False,
            server_default="anthropic",
        ),
    )
    op.drop_index("ix_agents_ai_model_id", table_name="agents")
    op.drop_constraint("fk_agents_ai_model_id", "agents", type_="foreignkey")
    op.drop_column("agents", "ai_model_id")
