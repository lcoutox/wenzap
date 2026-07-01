"""
Idempotent seed for billing plans and feature gates.

Run via: cd apps/api && uv run python scripts/seed_billing_plans.py

Safe to run multiple times: creates rows that don't exist, updates those that do.
Does not delete any existing data.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.plan_feature import PlanFeature

# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

_PLANS = [
    {
        "code": "starter",
        "name": "Free",
        "description": "Para empresas começando com IA.",
        "monthly_price_cents": 0,
        "currency": "BRL",
        "agents_limit": 1,
        "knowledge_bases_limit": 1,
        "sources_per_kb_limit": 20,
        "max_source_chars": 50_000,
        "max_file_size_bytes": 2_097_152,   # 2 MB
        "catalog_items_limit": 50,
        "channels_limit": 1,
        "users_limit": 3,
        "pipelines_limit": 1,
        "integrations_limit": 0,
        "monthly_ai_credits": 200,
        "monthly_conversations": 50,        # metric only, not a blocking quota
        "is_active": True,
        "is_public": True,
        "sort_order": 10,
    },
    {
        "code": "growth",
        "name": "Growth",
        "description": "Para começar a operar atendimento e vendas com agentes de IA.",
        "monthly_price_cents": 29_700,      # R$297/mês
        "currency": "BRL",
        "agents_limit": 3,
        "knowledge_bases_limit": 5,
        "sources_per_kb_limit": 100,
        "max_source_chars": 100_000,
        "max_file_size_bytes": 10_485_760,  # 10 MB
        "catalog_items_limit": 500,
        "channels_limit": 5,
        "users_limit": 5,
        "pipelines_limit": 3,
        "integrations_limit": 3,
        "monthly_ai_credits": 7_500,
        "monthly_conversations": 0,         # metric only
        "is_active": True,
        "is_public": True,
        "sort_order": 20,
    },
    # Scale and Enterprise limits below are PROVISIONAL.
    # A dedicated phase (Billing/Plans.Scale) will set definitive commercial values.
    {
        "code": "scale",
        "name": "Scale",
        "description": "Para operações em escala.",
        "monthly_price_cents": 29_900,      # PROVISIONAL — pending Scale phase
        "currency": "BRL",
        "agents_limit": 20,
        "knowledge_bases_limit": 20,
        "sources_per_kb_limit": 20,
        "max_source_chars": 50_000,
        "max_file_size_bytes": None,        # PROVISIONAL — pending Scale phase
        "catalog_items_limit": 50,
        "channels_limit": 20,
        "users_limit": 50,
        "pipelines_limit": 10,
        "integrations_limit": 10,
        "monthly_ai_credits": 20_000,
        "monthly_conversations": 0,         # metric only
        "is_active": True,
        "is_public": False,                 # internal — pending Scale phase
        "sort_order": 30,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "Limites customizados para grandes empresas.",
        "monthly_price_cents": 0,           # negotiated separately
        "currency": "BRL",
        "agents_limit": 999,
        "knowledge_bases_limit": 999,
        "sources_per_kb_limit": 999,
        "max_source_chars": 999_999,
        "max_file_size_bytes": None,        # negotiated separately
        "catalog_items_limit": 999_999,
        "channels_limit": 999,
        "users_limit": 999,
        "pipelines_limit": 999,
        "integrations_limit": 999,
        "monthly_ai_credits": 999_999,
        "monthly_conversations": 0,         # metric only
        "is_active": True,
        "is_public": False,                 # internal — negotiated separately
        "sort_order": 40,
    },
]


# ---------------------------------------------------------------------------
# Feature matrix
#
# Classification:
#   implemented/gated         — backend enforcement exists today
#   implemented/not yet gated — feature exists in product; gate pending enforcement
#   roadmap                   — feature not yet built
#   suspect/compatibility     — legacy key kept for compatibility; may merge or rename later
# ---------------------------------------------------------------------------

_FEATURE_MATRIX = [
    # ── starter ─────────────────────────────────────────────────────────────
    ("starter", "web_widget",               True),   # implemented/gated
    ("starter", "api",                      True),   # implemented/gated
    ("starter", "knowledge_base",           True),   # implemented/not yet gated
    ("starter", "catalog",                  True),   # implemented/not yet gated
    ("starter", "inbox",                    True),   # implemented/not yet gated
    ("starter", "playground",               True),   # implemented/not yet gated
    ("starter", "whatsapp",                 False),  # implemented/gated (blocked)
    ("starter", "instagram",                False),  # roadmap
    ("starter", "telegram",                 False),  # roadmap
    ("starter", "slack",                    False),  # roadmap
    ("starter", "pipelines",                False),  # implemented/not yet gated
    ("starter", "multiple_knowledge_bases", False),  # implemented/not yet gated
    ("starter", "whatsapp_channel",         False),  # suspect/compatibility
    ("starter", "api_access",               False),  # suspect/compatibility
    ("starter", "http_tools",               False),  # roadmap
    ("starter", "follow_up",                False),  # roadmap
    ("starter", "webhooks",                 False),  # roadmap
    ("starter", "custom_model",             False),  # roadmap
    ("starter", "analytics",               False),  # roadmap
    ("starter", "external_integrations",    False),  # roadmap
    ("starter", "remove_powered_by",        False),  # implemented/not yet gated
    ("starter", "premium_models",           False),  # roadmap
    # ── growth ──────────────────────────────────────────────────────────────
    ("growth",  "web_widget",               True),   # implemented/gated
    ("growth",  "api",                      True),   # implemented/gated
    ("growth",  "knowledge_base",           True),   # implemented/not yet gated
    ("growth",  "catalog",                  True),   # implemented/not yet gated
    ("growth",  "inbox",                    True),   # implemented/not yet gated
    ("growth",  "playground",               True),   # implemented/not yet gated
    ("growth",  "whatsapp",                 True),   # implemented/gated
    ("growth",  "pipelines",                True),   # implemented/not yet gated
    ("growth",  "multiple_knowledge_bases", True),   # implemented/not yet gated
    ("growth",  "whatsapp_channel",         True),   # suspect/compatibility
    ("growth",  "api_access",               True),   # suspect/compatibility
    ("growth",  "instagram",                False),  # roadmap
    ("growth",  "telegram",                 False),  # roadmap
    ("growth",  "slack",                    False),  # roadmap
    ("growth",  "http_tools",               False),  # roadmap
    ("growth",  "follow_up",                False),  # roadmap
    ("growth",  "webhooks",                 False),  # roadmap
    ("growth",  "custom_model",             False),  # roadmap
    ("growth",  "analytics",               False),  # roadmap
    ("growth",  "external_integrations",    False),  # roadmap
    ("growth",  "remove_powered_by",        False),  # implemented/not yet gated (Enterprise-only)
    ("growth",  "premium_models",           False),  # roadmap
    # ── scale ───────────────────────────────────────────────────────────────
    ("scale",   "web_widget",               True),   # implemented/gated
    ("scale",   "api",                      True),   # implemented/gated
    ("scale",   "knowledge_base",           True),   # implemented/not yet gated
    ("scale",   "catalog",                  True),   # implemented/not yet gated
    ("scale",   "inbox",                    True),   # implemented/not yet gated
    ("scale",   "playground",               True),   # implemented/not yet gated
    ("scale",   "whatsapp",                 True),   # implemented/gated
    ("scale",   "instagram",                True),   # roadmap (Scale+)
    ("scale",   "telegram",                 True),   # roadmap (Scale+)
    ("scale",   "pipelines",                True),   # implemented/not yet gated
    ("scale",   "multiple_knowledge_bases", True),   # implemented/not yet gated
    ("scale",   "whatsapp_channel",         True),   # suspect/compatibility
    ("scale",   "api_access",               True),   # suspect/compatibility
    ("scale",   "http_tools",               True),   # roadmap (Scale+)
    ("scale",   "follow_up",                True),   # roadmap (Scale+)
    ("scale",   "webhooks",                 True),   # roadmap (Scale+)
    ("scale",   "custom_model",             True),   # roadmap (Scale+)
    ("scale",   "analytics",               True),   # roadmap (Scale+)
    ("scale",   "external_integrations",    True),   # roadmap (Scale+)
    ("scale",   "premium_models",           True),   # roadmap (Scale+)
    ("scale",   "slack",                    False),  # roadmap (Enterprise-only)
    ("scale",   "remove_powered_by",        False),  # Enterprise-only
    # ── enterprise ──────────────────────────────────────────────────────────
    ("enterprise", "web_widget",               True),
    ("enterprise", "api",                      True),
    ("enterprise", "knowledge_base",           True),
    ("enterprise", "catalog",                  True),
    ("enterprise", "inbox",                    True),
    ("enterprise", "playground",               True),
    ("enterprise", "whatsapp",                 True),
    ("enterprise", "instagram",                True),
    ("enterprise", "telegram",                 True),
    ("enterprise", "slack",                    True),
    ("enterprise", "pipelines",                True),
    ("enterprise", "multiple_knowledge_bases", True),
    ("enterprise", "whatsapp_channel",         True),
    ("enterprise", "api_access",               True),
    ("enterprise", "http_tools",               True),
    ("enterprise", "follow_up",                True),
    ("enterprise", "webhooks",                 True),
    ("enterprise", "custom_model",             True),
    ("enterprise", "analytics",               True),
    ("enterprise", "external_integrations",    True),
    ("enterprise", "remove_powered_by",        True),  # Enterprise-only
    ("enterprise", "premium_models",           True),
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------


def seed_billing_plans(db: Session) -> None:
    """
    Upsert billing plans and feature gates.

    Safe to call multiple times: creates absent rows, updates existing ones.
    Never deletes rows. Relies on the caller to commit (or use autocommit).
    """
    _seed_plans(db)
    _seed_features(db)


def _seed_plans(db: Session) -> None:
    for data in _PLANS:
        plan = db.scalar(select(Plan).where(Plan.code == data["code"]))
        if plan is None:
            db.add(Plan(**data))
        else:
            for key, value in data.items():
                if key != "code":
                    setattr(plan, key, value)
    db.flush()


def _seed_features(db: Session) -> None:
    now = datetime.now(timezone.utc)
    for plan_code, feature_key, enabled in _FEATURE_MATRIX:
        row = db.scalar(
            select(PlanFeature).where(
                PlanFeature.plan_code == plan_code,
                PlanFeature.feature_key == feature_key,
            )
        )
        if row is None:
            db.add(PlanFeature(
                plan_code=plan_code,
                feature_key=feature_key,
                enabled=enabled,
                created_at=now,
            ))
        else:
            row.enabled = enabled
    db.flush()
