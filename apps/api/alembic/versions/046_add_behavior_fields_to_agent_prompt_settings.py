"""add behavior fields to agent_prompt_settings

Revision ID: 046
Revises: 045
Create Date: 2026-07-01
"""

import sqlalchemy as sa

from alembic import op

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add knowledge_only and show_sources booleans (not-null, safe defaults).
    op.add_column(
        "agent_prompt_settings",
        sa.Column("knowledge_only", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "agent_prompt_settings",
        sa.Column("show_sources", sa.Boolean(), nullable=False, server_default="false"),
    )

    # Add safe server-defaults for existing nullable columns so existing rows
    # get a predictable value without breaking NOT NULL constraints.
    # These stay nullable in Python — server_default only applies to INSERT,
    # not to ALTER of existing rows. We use UPDATE to backfill existing rows.
    op.execute(sa.text(
        "UPDATE agent_prompt_settings SET response_style = 'balanced' "
        "WHERE response_style IS NULL"
    ))
    op.execute(sa.text(
        "UPDATE agent_prompt_settings SET language_mode = 'auto' "
        "WHERE language_mode IS NULL"
    ))


def downgrade() -> None:
    op.drop_column("agent_prompt_settings", "show_sources")
    op.drop_column("agent_prompt_settings", "knowledge_only")
