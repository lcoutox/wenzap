"""update growth plan limits and price

Revision ID: 049
Revises: 048
Create Date: 2026-07-01

Plans.4: align Growth plan with product decision.
  - monthly_price_cents: 9900 → 29700  (R$297/mês)
  - agents_limit:        5    → 3
  - users_limit:         10   → 5
  - channels_limit:      (default) → 5
  - monthly_ai_credits:  5000 → 7500
  - catalog_items_limit: (default) → 500
  - sources_per_kb_limit: (default) → 100
  - max_source_chars:    (default) → 100000
  - max_file_size_bytes: (default) → 10485760  (10 MB)
  - monthly_conversations: 0 (not a blocking quota — metric only)

knowledge_bases_limit remains 5 (already correct).
"""

from alembic import op

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE plans
        SET
            name                 = 'Growth',
            description          = 'Para começar a operar atendimento e vendas com agentes de IA.',
            monthly_price_cents  = 29700,
            agents_limit         = 3,
            users_limit          = 5,
            knowledge_bases_limit = 5,
            sources_per_kb_limit = 100,
            max_source_chars     = 100000,
            max_file_size_bytes  = 10485760,
            catalog_items_limit  = 500,
            channels_limit       = 5,
            monthly_ai_credits   = 7500,
            monthly_conversations = 0,
            updated_at           = NOW()
        WHERE code = 'growth'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE plans
        SET
            name                 = 'Growth',
            description          = 'Para equipes em crescimento.',
            monthly_price_cents  = 9900,
            agents_limit         = 5,
            users_limit          = 10,
            knowledge_bases_limit = 5,
            sources_per_kb_limit = 20,
            max_source_chars     = 50000,
            max_file_size_bytes  = NULL,
            catalog_items_limit  = 50,
            channels_limit       = 1,
            monthly_ai_credits   = 5000,
            monthly_conversations = 2000,
            updated_at           = NOW()
        WHERE code = 'growth'
    """)
