"""seed ai model catalog

Revision ID: 011
Revises: 010
Create Date: 2026-06-22
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

# Fixed UUIDs for idempotent re-runs
_P_NEXBRAIN   = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
_P_ANTHROPIC  = str(uuid.UUID("00000000-0000-0000-0000-000000000002"))
_P_OPENAI     = str(uuid.UUID("00000000-0000-0000-0000-000000000003"))
_P_GOOGLE     = str(uuid.UUID("00000000-0000-0000-0000-000000000004"))

PROVIDERS = [
    {
        "id": _P_NEXBRAIN,
        "code": "nexbrain",
        "name": "Nexbrain",
        "description": "Modelos otimizados e pré-configurados pela plataforma Nexbrain.",
        "logo_url": None,
        "is_active": True,
    },
    {
        "id": _P_ANTHROPIC,
        "code": "anthropic",
        "name": "Anthropic",
        "description": "Criadora dos modelos Claude, focada em IA segura e confiável.",
        "logo_url": None,
        "is_active": True,
    },
    {
        "id": _P_OPENAI,
        "code": "openai",
        "name": "OpenAI",
        "description": "Criadora dos modelos GPT, pioneira em IA generativa.",
        "logo_url": None,
        "is_active": True,
    },
    {
        "id": _P_GOOGLE,
        "code": "google",
        "name": "Google",
        "description": "Criadora dos modelos Gemini, com forte integração ao ecossistema Google.",
        "logo_url": None,
        "is_active": True,
    },
]

MODELS = [
    # ── Nexbrain ──────────────────────────────────────────────────────────────
    {
        "id": str(uuid.UUID("00000000-0000-0000-0001-000000000001")),
        "provider_id": _P_NEXBRAIN,
        "code": "nexbrain-lite",
        "display_name": "Nexbrain Lite",
        "description": "Modelo econômico para tarefas simples e alto volume de mensagens.",
        "model_name": "nexbrain-lite",
        "credits_per_message": 1,
        "min_plan_code": "starter",
        "context_window_tokens": 32000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 1,
        "supports_vision": False,
        "supports_tools": True,
        "supports_reasoning": False,
        "supports_code": True,
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0001-000000000002")),
        "provider_id": _P_NEXBRAIN,
        "code": "nexbrain-prime",
        "display_name": "Nexbrain Prime",
        "description": "Equilíbrio entre custo e performance. Recomendado para a maioria.",
        "model_name": "nexbrain-prime",
        "credits_per_message": 2,
        "min_plan_code": "starter",
        "context_window_tokens": 128000,
        "is_default": True,
        "is_recommended": True,
        "is_featured": True,
        "is_active": True,
        "sort_order": 2,
        "supports_vision": False,
        "supports_tools": True,
        "supports_reasoning": True,
        "supports_code": True,
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0001-000000000003")),
        "provider_id": _P_NEXBRAIN,
        "code": "nexbrain-ultra",
        "display_name": "Nexbrain Ultra",
        "description": "Máxima capacidade de raciocínio e visão. Para casos de alta complexidade.",
        "model_name": "nexbrain-ultra",
        "credits_per_message": 8,
        "min_plan_code": "growth",
        "context_window_tokens": 200000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": True,
        "is_active": True,
        "sort_order": 3,
        "supports_vision": True,
        "supports_tools": True,
        "supports_reasoning": True,
        "supports_code": True,
    },
    # ── Anthropic ─────────────────────────────────────────────────────────────
    {
        "id": str(uuid.UUID("00000000-0000-0000-0002-000000000001")),
        "provider_id": _P_ANTHROPIC,
        "code": "claude-haiku",
        "display_name": "Claude Haiku",
        "description": "Modelo mais rápido e econômico da Anthropic. Ideal para alto volume.",
        "model_name": "claude-haiku-4-5",
        "credits_per_message": 1,
        "min_plan_code": "starter",
        "context_window_tokens": 200000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 10,
        "supports_vision": False,
        "supports_tools": True,
        "supports_reasoning": False,
        "supports_code": True,
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0002-000000000002")),
        "provider_id": _P_ANTHROPIC,
        "code": "claude-sonnet",
        "display_name": "Claude Sonnet",
        "description": "Equilíbrio entre inteligência e velocidade da Anthropic.",
        "model_name": "claude-sonnet-4-6",
        "credits_per_message": 3,
        "min_plan_code": "growth",
        "context_window_tokens": 200000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 11,
        "supports_vision": False,
        "supports_tools": True,
        "supports_reasoning": True,
        "supports_code": True,
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0002-000000000003")),
        "provider_id": _P_ANTHROPIC,
        "code": "claude-opus",
        "display_name": "Claude Opus",
        "description": "Modelo mais capaz da Anthropic. Para tarefas de alta complexidade.",
        "model_name": "claude-opus-4-8",
        "credits_per_message": 10,
        "min_plan_code": "scale",
        "context_window_tokens": 200000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 12,
        "supports_vision": True,
        "supports_tools": True,
        "supports_reasoning": True,
        "supports_code": True,
    },
    # ── OpenAI ────────────────────────────────────────────────────────────────
    {
        "id": str(uuid.UUID("00000000-0000-0000-0003-000000000001")),
        "provider_id": _P_OPENAI,
        "code": "gpt-mini",
        "display_name": "GPT Mini",
        "description": "Modelo econômico da OpenAI para tarefas rápidas e de alto volume.",
        "model_name": "gpt-4o-mini",
        "credits_per_message": 1,
        "min_plan_code": "starter",
        "context_window_tokens": 128000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 20,
        "supports_vision": True,
        "supports_tools": True,
        "supports_reasoning": False,
        "supports_code": True,
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0003-000000000002")),
        "provider_id": _P_OPENAI,
        "code": "gpt-advanced",
        "display_name": "GPT Advanced",
        "description": "Modelo mais capaz da OpenAI com visão e raciocínio avançado.",
        "model_name": "gpt-4o",
        "credits_per_message": 5,
        "min_plan_code": "growth",
        "context_window_tokens": 128000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 21,
        "supports_vision": True,
        "supports_tools": True,
        "supports_reasoning": True,
        "supports_code": True,
    },
    # ── Google ────────────────────────────────────────────────────────────────
    {
        "id": str(uuid.UUID("00000000-0000-0000-0004-000000000001")),
        "provider_id": _P_GOOGLE,
        "code": "gemini-flash",
        "display_name": "Gemini Flash",
        "description": "Modelo rápido e econômico do Google para tarefas de alto volume.",
        "model_name": "gemini-1.5-flash",
        "credits_per_message": 1,
        "min_plan_code": "starter",
        "context_window_tokens": 1000000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 30,
        "supports_vision": True,
        "supports_tools": True,
        "supports_reasoning": False,
        "supports_code": True,
    },
    {
        "id": str(uuid.UUID("00000000-0000-0000-0004-000000000002")),
        "provider_id": _P_GOOGLE,
        "code": "gemini-pro",
        "display_name": "Gemini Pro",
        "description": "Modelo mais capaz do Google com contexto de 1M tokens.",
        "model_name": "gemini-1.5-pro",
        "credits_per_message": 4,
        "min_plan_code": "growth",
        "context_window_tokens": 1000000,
        "is_default": False,
        "is_recommended": False,
        "is_featured": False,
        "is_active": True,
        "sort_order": 31,
        "supports_vision": True,
        "supports_tools": True,
        "supports_reasoning": True,
        "supports_code": True,
    },
]

_INSERT_PROVIDER = sa.text("""
    INSERT INTO ai_model_providers (id, code, name, description, logo_url, is_active)
    VALUES (:id, :code, :name, :description, :logo_url, :is_active)
    ON CONFLICT (code) DO NOTHING
""")

_INSERT_MODEL = sa.text("""
    INSERT INTO ai_models (
        id, provider_id, code, display_name, description, model_name,
        credits_per_message, min_plan_code, context_window_tokens,
        is_default, is_recommended, is_featured, is_active, sort_order,
        supports_vision, supports_tools, supports_reasoning, supports_code
    ) VALUES (
        :id, :provider_id, :code, :display_name, :description, :model_name,
        :credits_per_message, :min_plan_code, :context_window_tokens,
        :is_default, :is_recommended, :is_featured, :is_active, :sort_order,
        :supports_vision, :supports_tools, :supports_reasoning, :supports_code
    )
    ON CONFLICT (code) DO NOTHING
""")


def upgrade() -> None:
    for provider in PROVIDERS:
        op.execute(_INSERT_PROVIDER.bindparams(**provider))

    for model in MODELS:
        op.execute(_INSERT_MODEL.bindparams(**model))


def downgrade() -> None:
    provider_ids = [p["id"] for p in PROVIDERS]
    op.execute(
        sa.text("DELETE FROM ai_models WHERE provider_id = ANY(:ids)").bindparams(
            ids=provider_ids
        )
    )
    op.execute(
        sa.text("DELETE FROM ai_model_providers WHERE id = ANY(:ids)").bindparams(
            ids=provider_ids
        )
    )
