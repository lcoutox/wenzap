"""Add name_is_default to workspaces.

Tracks whether Workspace.name is still the auto-generated signup default
("Workspace de {first_name}") vs. something a member deliberately set — lets
onboarding safely sync the collected company_name into it without ever
clobbering a manual rename. New workspaces default to True (signup-time
name); update_workspace() flips it to False on any explicit rename.

Existing rows are backfilled to False (not True) deliberately — these
workspaces already exist in production and may already be customer-facing;
this feature is only meant to smooth first-time onboarding for new
signups, never to start silently renaming an established workspace.

Revision ID: 073
Revises: 072
Create Date: 2026-07-19
"""

import sqlalchemy as sa

from alembic import op

revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("name_is_default", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.execute("UPDATE workspaces SET name_is_default = false")
    op.alter_column("workspaces", "name_is_default", server_default=None)


def downgrade() -> None:
    op.drop_column("workspaces", "name_is_default")
