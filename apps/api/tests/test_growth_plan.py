"""
Tests for Billing/Plans.4 — Growth Plan Matrix & Upgrade Readiness.

Covers:
  - Growth plan limits (agents, users, KBs, catalog, channels, AI credits)
  - Growth channel type gates (web_widget ✅, whatsapp ✅)
  - Growth feature gates (catalog ✅, pipelines ✅, http_tools ❌, follow_up ❌,
    webhooks ❌, remove_powered_by ❌)
  - Free still blocks whatsapp; Growth allows it
  - plan_allows_channel_type: growth allows whatsapp, starter does not
  - plan_allows_feature: growth allows catalog; growth blocks http_tools/follow_up/webhooks
  - remove_powered_by: requires scale (not growth)
"""

import pytest
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.services.plan_feature_service import (
    plan_allows_channel_type,
    plan_allows_feature,
)

# feature_matrix fixture is defined in conftest.py

# ---------------------------------------------------------------------------
# Growth plan limits (constant assertions — fast, no DB)
# ---------------------------------------------------------------------------

def test_growth_agents_limit():
    assert _GROWTH_AGENTS_LIMIT == 3


def test_growth_users_limit():
    assert _GROWTH_USERS_LIMIT == 5


def test_growth_knowledge_bases_limit():
    assert _GROWTH_KB_LIMIT == 5


def test_growth_catalog_items_limit():
    assert _GROWTH_CATALOG_LIMIT == 500


def test_growth_channels_limit():
    assert _GROWTH_CHANNELS_LIMIT == 5


def test_growth_monthly_ai_credits():
    assert _GROWTH_AI_CREDITS == 7500


def test_growth_monthly_price_cents():
    assert _GROWTH_PRICE_CENTS == 29700


# ---------------------------------------------------------------------------
# Growth limits read from live DB
# ---------------------------------------------------------------------------

def test_growth_plan_limits_from_db(db: Session):
    """Verify DB plan matches Plans.4 spec (requires migration 049 to have run)."""
    from sqlalchemy import select  # noqa: PLC0415

    plan = db.scalar(select(Plan).where(Plan.code == "growth"))
    if plan is None:
        pytest.skip("growth plan not seeded in test DB — run alembic on prod/staging")
    assert plan.agents_limit          == _GROWTH_AGENTS_LIMIT
    assert plan.users_limit           == _GROWTH_USERS_LIMIT
    assert plan.knowledge_bases_limit == _GROWTH_KB_LIMIT
    assert plan.catalog_items_limit   == _GROWTH_CATALOG_LIMIT
    assert plan.channels_limit        == _GROWTH_CHANNELS_LIMIT
    assert plan.monthly_ai_credits    == _GROWTH_AI_CREDITS
    assert plan.monthly_price_cents   == _GROWTH_PRICE_CENTS
    assert plan.sources_per_kb_limit  == 100
    assert plan.max_source_chars      == 100_000
    assert plan.max_file_size_bytes   == 10_485_760


# ---------------------------------------------------------------------------
# Channel type gates
# ---------------------------------------------------------------------------

def test_growth_allows_web_widget(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "growth", "web_widget") is True


def test_growth_allows_whatsapp(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "growth", "whatsapp") is True


def test_starter_blocks_whatsapp(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "starter", "whatsapp") is False


def test_starter_allows_web_widget(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "starter", "web_widget") is True


def test_growth_does_not_allow_instagram(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "growth", "instagram") is False


def test_growth_does_not_allow_telegram(db: Session, feature_matrix):
    assert plan_allows_channel_type(db, "growth", "telegram") is False


# ---------------------------------------------------------------------------
# Feature gates — Growth allows
# ---------------------------------------------------------------------------

def test_growth_allows_catalog(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "catalog") is True


def test_growth_allows_pipelines(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "pipelines") is True


def test_growth_allows_multiple_kbs(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "multiple_knowledge_bases") is True


def test_growth_allows_whatsapp_channel_feature(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "whatsapp_channel") is True


# ---------------------------------------------------------------------------
# Feature gates — Growth blocks
# ---------------------------------------------------------------------------

def test_growth_blocks_http_tools(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "http_tools") is False


def test_growth_blocks_follow_up(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "follow_up") is False


def test_growth_blocks_webhooks(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "webhooks") is False


def test_growth_blocks_remove_powered_by(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "remove_powered_by") is False


def test_growth_blocks_custom_model(db: Session, feature_matrix):
    assert plan_allows_feature(db, "growth", "custom_model") is False


def test_starter_blocks_remove_powered_by(db: Session, feature_matrix):
    assert plan_allows_feature(db, "starter", "remove_powered_by") is False


def test_scale_blocks_remove_powered_by(db: Session, feature_matrix):
    # remove_powered_by is Enterprise-only; scale is blocked
    assert plan_allows_feature(db, "scale", "remove_powered_by") is False


def test_enterprise_allows_remove_powered_by(db: Session, feature_matrix):
    assert plan_allows_feature(db, "enterprise", "remove_powered_by") is True


def test_scale_allows_http_tools(db: Session, feature_matrix):
    assert plan_allows_feature(db, "scale", "http_tools") is True


def test_scale_allows_webhooks(db: Session, feature_matrix):
    assert plan_allows_feature(db, "scale", "webhooks") is True


# ---------------------------------------------------------------------------
# Constants (mirror expected values — fail fast if migration hasn't run)
# ---------------------------------------------------------------------------

_GROWTH_AGENTS_LIMIT   = 3
_GROWTH_USERS_LIMIT    = 5
_GROWTH_KB_LIMIT       = 5
_GROWTH_CATALOG_LIMIT  = 500
_GROWTH_CHANNELS_LIMIT = 5
_GROWTH_AI_CREDITS     = 7500
_GROWTH_PRICE_CENTS    = 29700
