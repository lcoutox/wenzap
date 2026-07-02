"""Add origin/last_seen_at to contacts and create contact_variables.

Revision ID: 054
Revises: 053
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── contacts: new fields ──────────────────────────────────────────────────
    op.add_column("contacts", sa.Column("origin", sa.String(100), nullable=True))
    op.add_column("contacts", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))

    # Dedup indexes: unique email/phone per workspace (partial — ignore NULLs).
    op.create_index(
        "ix_contacts_workspace_email",
        "contacts",
        ["workspace_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "ix_contacts_workspace_phone",
        "contacts",
        ["workspace_id", "phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )

    # ── contact_variables ─────────────────────────────────────────────────────
    op.create_table(
        "contact_variables",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
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
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contact_id", "key", name="uq_contact_variables_contact_key"),
    )
    op.create_index("ix_contact_variables_contact_id", "contact_variables", ["contact_id"])
    op.create_index("ix_contact_variables_workspace_id", "contact_variables", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_contact_variables_workspace_id", table_name="contact_variables")
    op.drop_index("ix_contact_variables_contact_id", table_name="contact_variables")
    op.drop_table("contact_variables")
    op.drop_index("ix_contacts_workspace_phone", table_name="contacts")
    op.drop_index("ix_contacts_workspace_email", table_name="contacts")
    op.drop_column("contacts", "last_seen_at")
    op.drop_column("contacts", "origin")
