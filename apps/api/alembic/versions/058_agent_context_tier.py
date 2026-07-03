"""agent_context_tier

Backfill and harden the context_window_tier column that was created nullable
in migration 016 but never populated.

Steps:
  1. Backfill all existing rows to 'standard' (the sensible default for
     agents that pre-date context tier configuration).
  2. Add NOT NULL constraint with server-side default 'standard'.

Revision ID: 058
Revises: 057
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: backfill rows created before this migration
    op.execute(
        "UPDATE agent_model_settings "
        "SET context_window_tier = 'standard' "
        "WHERE context_window_tier IS NULL"
    )

    # Step 2: harden — set NOT NULL with server-side default
    op.alter_column(
        "agent_model_settings",
        "context_window_tier",
        existing_type=sa.String(20),
        nullable=False,
        server_default="standard",
    )


def downgrade() -> None:
    op.alter_column(
        "agent_model_settings",
        "context_window_tier",
        existing_type=sa.String(20),
        nullable=True,
        server_default=None,
    )
    op.execute(
        "UPDATE agent_model_settings SET context_window_tier = NULL"
    )
