"""
Tests for billing plans seed — Billing/Plans.4.1.

Verifies:
  - seed creates absent plans
  - seed updates existing plans
  - seed creates absent plan_features
  - seed updates existing plan_features
  - seed is idempotent (running twice yields same state)
  - canonical matrix values after seed
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.plan_feature import PlanFeature
from app.seeds.billing_plans import seed_billing_plans


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


def test_seed_creates_plans_when_absent(db: Session):
    seed_billing_plans(db)
    db.commit()

    codes = {row.code for row in db.scalars(select(Plan)).all()}
    assert {"starter", "growth", "scale", "enterprise"} <= codes


def test_seed_updates_existing_plan(db: Session):
    existing = Plan(
        code="starter",
        name="Old Name",
        monthly_price_cents=9999,
        currency="BRL",
        agents_limit=99,
        knowledge_bases_limit=99,
        users_limit=99,
        pipelines_limit=99,
        integrations_limit=99,
        channels_limit=99,
        monthly_ai_credits=99999,
        monthly_conversations=99999,
        is_active=True,
    )
    db.add(existing)
    db.commit()

    seed_billing_plans(db)
    db.commit()
    db.refresh(existing)

    assert existing.name == "Free"
    assert existing.monthly_price_cents == 0
    assert existing.agents_limit == 1
    assert existing.monthly_ai_credits == 200


def test_seed_starter_limits(db: Session):
    seed_billing_plans(db)
    db.commit()

    plan = db.scalar(select(Plan).where(Plan.code == "starter"))
    assert plan is not None
    assert plan.agents_limit == 1
    assert plan.users_limit == 3
    assert plan.knowledge_bases_limit == 1
    assert plan.channels_limit == 1
    assert plan.monthly_ai_credits == 200
    assert plan.max_file_size_bytes == 2_097_152


def test_seed_growth_limits(db: Session):
    seed_billing_plans(db)
    db.commit()

    plan = db.scalar(select(Plan).where(Plan.code == "growth"))
    assert plan is not None
    assert plan.agents_limit == 3
    assert plan.users_limit == 5
    assert plan.knowledge_bases_limit == 5
    assert plan.channels_limit == 5
    assert plan.monthly_ai_credits == 7_500
    assert plan.monthly_price_cents == 29_700
    assert plan.max_file_size_bytes == 10_485_760


# ---------------------------------------------------------------------------
# Plan features
# ---------------------------------------------------------------------------


def test_seed_creates_features_when_absent(db: Session):
    seed_billing_plans(db)
    db.commit()

    rows = db.scalars(select(PlanFeature)).all()
    assert len(rows) >= 88  # 4 plans × 22 features


def test_seed_updates_existing_feature(db: Session):
    seed_billing_plans(db)
    db.commit()

    row = db.scalar(select(PlanFeature).where(
        PlanFeature.plan_code == "starter",
        PlanFeature.feature_key == "catalog",
    ))
    assert row is not None
    row.enabled = False
    db.commit()

    seed_billing_plans(db)
    db.commit()
    db.refresh(row)

    assert row.enabled is True  # seed restores canonical value


def test_seed_starter_is_public(db: Session):
    seed_billing_plans(db)
    plan = db.scalar(select(Plan).where(Plan.code == "starter"))
    assert plan.is_public is True
    assert plan.sort_order == 10


def test_seed_growth_is_public(db: Session):
    seed_billing_plans(db)
    plan = db.scalar(select(Plan).where(Plan.code == "growth"))
    assert plan.is_public is True
    assert plan.sort_order == 20


def test_seed_scale_is_not_public(db: Session):
    seed_billing_plans(db)
    plan = db.scalar(select(Plan).where(Plan.code == "scale"))
    assert plan.is_public is False
    assert plan.sort_order == 30


def test_seed_enterprise_is_not_public(db: Session):
    seed_billing_plans(db)
    plan = db.scalar(select(Plan).where(Plan.code == "enterprise"))
    assert plan.is_public is False
    assert plan.sort_order == 40


def test_all_plans_remain_active(db: Session):
    seed_billing_plans(db)
    plans = db.scalars(select(Plan)).all()
    assert all(p.is_active for p in plans)


def test_seed_is_idempotent(db: Session):
    seed_billing_plans(db)
    db.commit()

    count_after_first = db.query(Plan).count()
    feature_count_after_first = db.query(PlanFeature).count()

    seed_billing_plans(db)
    db.commit()

    assert db.query(Plan).count() == count_after_first
    assert db.query(PlanFeature).count() == feature_count_after_first


# ---------------------------------------------------------------------------
# Canonical matrix assertions
# ---------------------------------------------------------------------------


def _feature(db: Session, plan_code: str, feature_key: str) -> bool:
    row = db.scalar(select(PlanFeature).where(
        PlanFeature.plan_code == plan_code,
        PlanFeature.feature_key == feature_key,
    ))
    return row.enabled if row else False


def test_free_catalog_permitted(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "starter", "catalog") is True


def test_free_whatsapp_blocked(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "starter", "whatsapp") is False


def test_free_remove_powered_by_blocked(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "starter", "remove_powered_by") is False


def test_growth_whatsapp_permitted(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "growth", "whatsapp") is True


def test_growth_remove_powered_by_blocked(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "growth", "remove_powered_by") is False


def test_scale_blocks_remove_powered_by(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "scale", "remove_powered_by") is False


def test_enterprise_allows_remove_powered_by(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "enterprise", "remove_powered_by") is True


def test_scale_allows_http_tools(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "scale", "http_tools") is True


def test_growth_blocks_http_tools(db: Session):
    seed_billing_plans(db)
    assert _feature(db, "growth", "http_tools") is False
