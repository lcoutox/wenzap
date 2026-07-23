"""Add workspace_credentials table.

whatsapp-voice-groq-elevenlabs-prd.md — customer-supplied API keys (Groq,
ElevenLabs) scoped per workspace, not per channel. Sibling of
channel_credentials but without channel_id, since these aren't tied to a
specific WhatsApp channel.

Revision ID: 077
Revises: 076
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "077"
down_revision = "076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("workspace_id", "provider", name="uq_workspace_credentials_ws_provider"),
    )
    op.create_index(
        "ix_workspace_credentials_workspace_id", "workspace_credentials", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_credentials_workspace_id", table_name="workspace_credentials")
    op.drop_table("workspace_credentials")
