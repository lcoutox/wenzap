"""create channel_credentials table

Revision ID: 039
Revises: 038
Create Date: 2026-06-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None

_uuid = sa.text("gen_random_uuid()")
_now = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "channel_credentials",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=_uuid,
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_id",
            sa.UUID(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # e.g. "meta_cloud_api"
        sa.Column("provider", sa.String(50), nullable=False),
        # e.g. "whatsapp_user_access_token"
        sa.Column("credential_type", sa.String(80), nullable=False),
        # Fernet-encrypted value — never store plaintext here
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        # Optional metadata: token_type, scopes, waba_id, etc.
        sa.Column("metadata_json", JSONB(), nullable=True),
        # NULL means the token has no known expiry (e.g. system user tokens)
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # How the credential was obtained: "embedded_signup" | "manual" | "test"
        sa.Column("obtained_via", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_now,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_now,
            nullable=False,
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        # One active credential per channel/provider/type combination.
        sa.UniqueConstraint(
            "channel_id",
            "provider",
            "credential_type",
            name="uq_channel_credentials_channel_provider_type",
        ),
    )

    op.create_index(
        "ix_channel_credentials_channel_id",
        "channel_credentials",
        ["channel_id"],
    )
    op.create_index(
        "ix_channel_credentials_workspace_id",
        "channel_credentials",
        ["workspace_id"],
    )
    op.create_index(
        "ix_channel_credentials_provider",
        "channel_credentials",
        ["provider"],
    )
    op.create_index(
        "ix_channel_credentials_credential_type",
        "channel_credentials",
        ["credential_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_channel_credentials_credential_type", "channel_credentials")
    op.drop_index("ix_channel_credentials_provider", "channel_credentials")
    op.drop_index("ix_channel_credentials_workspace_id", "channel_credentials")
    op.drop_index("ix_channel_credentials_channel_id", "channel_credentials")
    op.drop_table("channel_credentials")
