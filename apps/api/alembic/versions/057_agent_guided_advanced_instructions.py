"""agent guided advanced instructions

Revision ID: 057
Revises: 056
Create Date: 2026-07-03

Adds instructions_mode, guided_config, and advanced_prompt to agent_prompt_settings.
Migrates existing rows: agents with a system_prompt become 'advanced'; others stay 'guided'.
Legacy system_prompt and persona columns are NOT removed.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns (nullable first so existing rows don't fail)
    op.add_column(
        "agent_prompt_settings",
        sa.Column("instructions_mode", sa.String(20), nullable=True),
    )
    op.add_column(
        "agent_prompt_settings",
        sa.Column("guided_config", JSONB, nullable=True),
    )
    op.add_column(
        "agent_prompt_settings",
        sa.Column("advanced_prompt", sa.Text, nullable=True),
    )

    # Data migration: rows with system_prompt AND/OR persona -> advanced mode
    # Case 1: both system_prompt and persona set -> join them
    op.execute("""
        UPDATE agent_prompt_settings
        SET
            instructions_mode = 'advanced',
            advanced_prompt = 'Persona: ' || trim(persona) || E'\n\n' || trim(system_prompt)
        WHERE (system_prompt IS NOT NULL AND trim(system_prompt) != '')
          AND (persona IS NOT NULL AND trim(persona) != '')
    """)

    # Case 2: only system_prompt set
    op.execute("""
        UPDATE agent_prompt_settings
        SET
            instructions_mode = 'advanced',
            advanced_prompt = trim(system_prompt)
        WHERE (system_prompt IS NOT NULL AND trim(system_prompt) != '')
          AND (persona IS NULL OR trim(persona) = '')
    """)

    # Case 3: only persona set (system_prompt empty/null)
    op.execute("""
        UPDATE agent_prompt_settings
        SET
            instructions_mode = 'advanced',
            advanced_prompt = 'Persona: ' || trim(persona)
        WHERE (system_prompt IS NULL OR trim(system_prompt) = '')
          AND (persona IS NOT NULL AND trim(persona) != '')
    """)

    # Case 4: both empty -> guided mode with empty config
    op.execute("""
        UPDATE agent_prompt_settings
        SET
            instructions_mode = 'guided',
            guided_config = NULL
        WHERE (system_prompt IS NULL OR trim(system_prompt) = '')
          AND (persona IS NULL OR trim(persona) = '')
    """)

    # Now make instructions_mode NOT NULL with default
    op.alter_column(
        "agent_prompt_settings",
        "instructions_mode",
        nullable=False,
        server_default="guided",
    )


def downgrade() -> None:
    op.drop_column("agent_prompt_settings", "advanced_prompt")
    op.drop_column("agent_prompt_settings", "guided_config")
    op.drop_column("agent_prompt_settings", "instructions_mode")
