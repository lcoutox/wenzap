"""reseed full ai model catalog with missing providers and models

Revision ID: 015
Revises: 014
Create Date: 2026-06-22
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Insert missing providers (gen_random_uuid() avoids PK conflicts)
    missing_providers = [
        {"code": "nexbrain", "name": "Nexbrain",
         "description": "Modelos otimizados e pré-configurados pela plataforma Nexbrain."},
        {"code": "openai", "name": "OpenAI",
         "description": "Criadora dos modelos GPT, pioneira em IA generativa."},
        {"code": "google", "name": "Google",
         "description": "Criadora dos modelos Gemini, com forte integração ao ecossistema Google."},
    ]
    for p in missing_providers:
        conn.execute(sa.text("""
            INSERT INTO ai_model_providers (id, code, name, description, logo_url, is_active)
            VALUES (gen_random_uuid(), :code, :name, :description, NULL, TRUE)
            ON CONFLICT (code) DO NOTHING
        """), p)

    # 2. Upsert all models, resolving provider_id by code
    models = [
        # ── Nexbrain ─────────────────────────────────────────────────────────
        {"provider_code": "nexbrain", "code": "nexbrain-lite",
         "display_name": "Nexbrain Lite",
         "description": "Modelo econômico para tarefas simples e alto volume de mensagens.",
         "model_name": "nexbrain-lite", "credits": 1, "plan": "starter",
         "ctx": 32000, "default": False, "recommended": False, "featured": False,
         "sort": 1, "vision": False, "tools": True, "reason": False, "code_": True},
        {"provider_code": "nexbrain", "code": "nexbrain-prime",
         "display_name": "Nexbrain Prime",
         "description": "Equilíbrio entre custo e performance. Recomendado para a maioria.",
         "model_name": "nexbrain-prime", "credits": 2, "plan": "starter",
         "ctx": 128000, "default": True, "recommended": True, "featured": True,
         "sort": 2, "vision": False, "tools": True, "reason": True, "code_": True},
        {"provider_code": "nexbrain", "code": "nexbrain-ultra",
         "display_name": "Nexbrain Ultra",
         "description": "Máxima capacidade de raciocínio e visão. Para casos de alta complexidade.",
         "model_name": "nexbrain-ultra", "credits": 8, "plan": "growth",
         "ctx": 200000, "default": False, "recommended": False, "featured": True,
         "sort": 3, "vision": True, "tools": True, "reason": True, "code_": True},
        # ── Anthropic ─────────────────────────────────────────────────────────
        {"provider_code": "anthropic", "code": "claude-haiku",
         "display_name": "Claude Haiku",
         "description": "Modelo mais rápido e econômico da Anthropic. Ideal para alto volume.",
         "model_name": "claude-haiku-4-5", "credits": 1, "plan": "starter",
         "ctx": 200000, "default": False, "recommended": False, "featured": False,
         "sort": 10, "vision": False, "tools": True, "reason": False, "code_": True},
        {"provider_code": "anthropic", "code": "claude-sonnet",
         "display_name": "Claude Sonnet",
         "description": "Equilíbrio entre inteligência e velocidade da Anthropic.",
         "model_name": "claude-sonnet-4-6", "credits": 3, "plan": "growth",
         "ctx": 200000, "default": False, "recommended": False, "featured": False,
         "sort": 11, "vision": False, "tools": True, "reason": True, "code_": True},
        {"provider_code": "anthropic", "code": "claude-opus",
         "display_name": "Claude Opus",
         "description": "Modelo mais capaz da Anthropic. Para tarefas de alta complexidade.",
         "model_name": "claude-opus-4-8", "credits": 10, "plan": "scale",
         "ctx": 200000, "default": False, "recommended": False, "featured": False,
         "sort": 12, "vision": True, "tools": True, "reason": True, "code_": True},
        # ── OpenAI ────────────────────────────────────────────────────────────
        {"provider_code": "openai", "code": "gpt-mini",
         "display_name": "GPT Mini",
         "description": "Modelo econômico da OpenAI para tarefas rápidas e de alto volume.",
         "model_name": "gpt-4o-mini", "credits": 1, "plan": "starter",
         "ctx": 128000, "default": False, "recommended": False, "featured": False,
         "sort": 20, "vision": True, "tools": True, "reason": False, "code_": True},
        {"provider_code": "openai", "code": "gpt-advanced",
         "display_name": "GPT Advanced",
         "description": "Modelo mais capaz da OpenAI com visão e raciocínio avançado.",
         "model_name": "gpt-4o", "credits": 5, "plan": "growth",
         "ctx": 128000, "default": False, "recommended": False, "featured": False,
         "sort": 21, "vision": True, "tools": True, "reason": True, "code_": True},
        # ── Google ────────────────────────────────────────────────────────────
        {"provider_code": "google", "code": "gemini-flash",
         "display_name": "Gemini Flash",
         "description": "Modelo rápido e econômico do Google para tarefas de alto volume.",
         "model_name": "gemini-1.5-flash", "credits": 1, "plan": "starter",
         "ctx": 1000000, "default": False, "recommended": False, "featured": False,
         "sort": 30, "vision": True, "tools": True, "reason": False, "code_": True},
        {"provider_code": "google", "code": "gemini-pro",
         "display_name": "Gemini Pro",
         "description": "Modelo mais capaz do Google com contexto de 1M tokens.",
         "model_name": "gemini-1.5-pro", "credits": 4, "plan": "growth",
         "ctx": 1000000, "default": False, "recommended": False, "featured": False,
         "sort": 31, "vision": True, "tools": True, "reason": True, "code_": True},
    ]

    for m in models:
        conn.execute(sa.text("""
            INSERT INTO ai_models (
                id, provider_id, code, display_name, description, model_name,
                credits_per_message, min_plan_code, context_window_tokens,
                is_default, is_recommended, is_featured, is_active, sort_order,
                supports_vision, supports_tools, supports_reasoning, supports_code
            )
            SELECT
                gen_random_uuid(),
                p.id,
                :code, :display_name, :description, :model_name,
                :credits, :plan, :ctx,
                :default, :recommended, :featured, TRUE, :sort,
                :vision, :tools, :reason, :code_
            FROM ai_model_providers p WHERE p.code = :provider_code
            ON CONFLICT (code) DO UPDATE SET
                display_name          = EXCLUDED.display_name,
                description           = EXCLUDED.description,
                model_name            = EXCLUDED.model_name,
                credits_per_message   = EXCLUDED.credits_per_message,
                min_plan_code         = EXCLUDED.min_plan_code,
                context_window_tokens = EXCLUDED.context_window_tokens,
                is_default            = EXCLUDED.is_default,
                is_recommended        = EXCLUDED.is_recommended,
                is_featured           = EXCLUDED.is_featured,
                sort_order            = EXCLUDED.sort_order,
                supports_vision       = EXCLUDED.supports_vision,
                supports_tools        = EXCLUDED.supports_tools,
                supports_reasoning    = EXCLUDED.supports_reasoning,
                supports_code         = EXCLUDED.supports_code
        """), m)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        DELETE FROM ai_model_providers WHERE code IN ('nexbrain', 'openai', 'google')
    """))
