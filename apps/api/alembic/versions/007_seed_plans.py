"""seed plans

Revision ID: 007
Revises: 006
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

PLANS = [
    {
        "code": "starter",
        "name": "Starter",
        "description": "Para empresas começando com IA.",
        "monthly_price_cents": 0,
        "agents_limit": 1,
        "knowledge_bases_limit": 1,
        "users_limit": 3,
        "pipelines_limit": 1,
        "integrations_limit": 0,
        "monthly_ai_credits": 500,
        "monthly_conversations": 200,
    },
    {
        "code": "growth",
        "name": "Growth",
        "description": "Para equipes em crescimento.",
        "monthly_price_cents": 9900,
        "agents_limit": 5,
        "knowledge_bases_limit": 5,
        "users_limit": 10,
        "pipelines_limit": 3,
        "integrations_limit": 3,
        "monthly_ai_credits": 5000,
        "monthly_conversations": 2000,
    },
    {
        "code": "scale",
        "name": "Scale",
        "description": "Para operações em escala.",
        "monthly_price_cents": 29900,
        "agents_limit": 20,
        "knowledge_bases_limit": 20,
        "users_limit": 50,
        "pipelines_limit": 10,
        "integrations_limit": 10,
        "monthly_ai_credits": 20000,
        "monthly_conversations": 10000,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "Limites customizados para grandes empresas.",
        "monthly_price_cents": 0,
        "agents_limit": 999,
        "knowledge_bases_limit": 999,
        "users_limit": 999,
        "pipelines_limit": 999,
        "integrations_limit": 999,
        "monthly_ai_credits": 999999,
        "monthly_conversations": 999999,
    },
]


def upgrade() -> None:
    for plan in PLANS:
        op.execute(
            sa.text("""
                INSERT INTO plans (code, name, description, monthly_price_cents, currency,
                    agents_limit, knowledge_bases_limit, users_limit, pipelines_limit,
                    integrations_limit, monthly_ai_credits, monthly_conversations, is_active)
                VALUES (:code, :name, :description, :monthly_price_cents, 'BRL',
                    :agents_limit, :knowledge_bases_limit, :users_limit, :pipelines_limit,
                    :integrations_limit, :monthly_ai_credits, :monthly_conversations, true)
                ON CONFLICT (code) DO NOTHING
            """).bindparams(**plan)
        )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE code IN ('starter', 'growth', 'scale', 'enterprise')")
