"""Add voice_reply_enabled and elevenlabs_voice_id to agent_prompt_settings.

whatsapp-voice-groq-elevenlabs-prd.md — per-agent toggle for replying with a
synthesized voice message when the triggering inbound message was itself a
voice note. Same place as response_style/reply_delay_seconds: agent
configuration, not an LLM-invoked tool (it's automatic based on message type).

Revision ID: 078
Revises: 077
Create Date: 2026-07-23
"""

import sqlalchemy as sa

from alembic import op

revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_prompt_settings",
        sa.Column("voice_reply_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "agent_prompt_settings",
        sa.Column("elevenlabs_voice_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_prompt_settings", "elevenlabs_voice_id")
    op.drop_column("agent_prompt_settings", "voice_reply_enabled")
