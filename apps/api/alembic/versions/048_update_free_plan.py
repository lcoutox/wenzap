"""update starter plan to Free with revised limits

Revision ID: 048
Revises: 047
Create Date: 2026-07-01
"""

from alembic import op

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE plans
        SET
            name = 'Free',
            knowledge_bases_limit = 1,
            monthly_ai_credits = 200,
            monthly_conversations = 50,
            updated_at = NOW()
        WHERE code = 'starter'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE plans
        SET
            name = 'Starter',
            knowledge_bases_limit = 2,
            monthly_ai_credits = 500,
            monthly_conversations = 200,
            updated_at = NOW()
        WHERE code = 'starter'
    """)
