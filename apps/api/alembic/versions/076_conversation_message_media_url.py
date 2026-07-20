"""Add media_url to conversation_messages.

conversation-image-upload-prd.md — storage key for an inbound image (or
future media type), resolved via StorageProvider at read time. Nullable:
only set for content_type="image" (or future media types); every existing
text message keeps media_url=NULL with no backfill needed.

Revision ID: 076
Revises: 075
Create Date: 2026-07-20
"""

import sqlalchemy as sa

from alembic import op

revision = "076"
down_revision = "075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("media_url", sa.String(1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "media_url")
