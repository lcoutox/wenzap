"""create contacts table

Revision ID: 030
Revises: 029
Create Date: 2026-06-23
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("email", sa.String(300), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("external_id", sa.String(300), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_workspace_id", "contacts", ["workspace_id"])
    # Partial index for external_id lookups (only rows with a value)
    op.create_index(
        "ix_contacts_workspace_external_id",
        "contacts",
        ["workspace_id", "external_id"],
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_contacts_workspace_external_id", table_name="contacts")
    op.drop_index("ix_contacts_workspace_id", table_name="contacts")
    op.drop_table("contacts")
