"""create plan_features table and seed initial matrix

Revision ID: 050
Revises: 049
Create Date: 2026-07-01

Feature gates matrix — all plans × all feature keys.
plan_code has a FK referencing plans.code (unique).

Plans starter/growth/scale/enterprise are guaranteed to exist
from migration 007_seed_plans.
"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None

# Full feature matrix: (plan_code, feature_key, enabled)
_MATRIX = [
    # ── starter ─────────────────────────────────────────────────────────────
    ("starter", "web_widget",               True),
    ("starter", "api",                      True),
    ("starter", "knowledge_base",           True),
    ("starter", "inbox",                    True),
    ("starter", "playground",               True),
    ("starter", "catalog",                  True),   # starter: catalog enabled (limited qty)
    ("starter", "whatsapp",                 False),
    ("starter", "instagram",                False),
    ("starter", "telegram",                 False),
    ("starter", "slack",                    False),
    ("starter", "pipelines",                False),
    ("starter", "multiple_knowledge_bases", False),
    ("starter", "whatsapp_channel",         False),
    ("starter", "api_access",               False),
    ("starter", "http_tools",               False),
    ("starter", "follow_up",                False),
    ("starter", "webhooks",                 False),
    ("starter", "custom_model",             False),
    ("starter", "analytics",                False),
    ("starter", "external_integrations",    False),
    ("starter", "remove_powered_by",        False),
    ("starter", "premium_models",           False),
    # ── growth ──────────────────────────────────────────────────────────────
    ("growth",  "web_widget",               True),
    ("growth",  "api",                      True),
    ("growth",  "knowledge_base",           True),
    ("growth",  "inbox",                    True),
    ("growth",  "playground",               True),
    ("growth",  "catalog",                  True),
    ("growth",  "whatsapp",                 True),
    ("growth",  "pipelines",                True),
    ("growth",  "multiple_knowledge_bases", True),
    ("growth",  "whatsapp_channel",         True),
    ("growth",  "api_access",               True),
    ("growth",  "instagram",                False),
    ("growth",  "telegram",                 False),
    ("growth",  "slack",                    False),
    ("growth",  "http_tools",               False),
    ("growth",  "follow_up",                False),
    ("growth",  "webhooks",                 False),
    ("growth",  "custom_model",             False),
    ("growth",  "analytics",                False),
    ("growth",  "external_integrations",    False),
    ("growth",  "remove_powered_by",        False),
    ("growth",  "premium_models",           False),
    # ── scale ───────────────────────────────────────────────────────────────
    ("scale",   "web_widget",               True),
    ("scale",   "api",                      True),
    ("scale",   "knowledge_base",           True),
    ("scale",   "inbox",                    True),
    ("scale",   "playground",               True),
    ("scale",   "catalog",                  True),
    ("scale",   "whatsapp",                 True),
    ("scale",   "instagram",                True),
    ("scale",   "telegram",                 True),
    ("scale",   "pipelines",                True),
    ("scale",   "multiple_knowledge_bases", True),
    ("scale",   "whatsapp_channel",         True),
    ("scale",   "api_access",               True),
    ("scale",   "http_tools",               True),
    ("scale",   "follow_up",                True),
    ("scale",   "webhooks",                 True),
    ("scale",   "custom_model",             True),
    ("scale",   "analytics",                True),
    ("scale",   "external_integrations",    True),
    ("scale",   "premium_models",           True),
    ("scale",   "slack",                    False),
    ("scale",   "remove_powered_by",        False),  # Enterprise-only
    # ── enterprise ──────────────────────────────────────────────────────────
    ("enterprise", "web_widget",               True),
    ("enterprise", "api",                      True),
    ("enterprise", "knowledge_base",           True),
    ("enterprise", "inbox",                    True),
    ("enterprise", "playground",               True),
    ("enterprise", "catalog",                  True),
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
    ("enterprise", "analytics",                True),
    ("enterprise", "external_integrations",    True),
    ("enterprise", "remove_powered_by",        True),  # Enterprise-only
    ("enterprise", "premium_models",           True),
]


def upgrade() -> None:
    op.create_table(
        "plan_features",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("plan_code", sa.String(50), nullable=False),
        sa.Column("feature_key", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["plan_code"], ["plans.code"],
            name="fk_plan_features_plan_code",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("plan_code", "feature_key", name="uq_plan_features_plan_feature"),
    )
    op.create_index("ix_plan_features_plan_code", "plan_features", ["plan_code"])
    op.create_index("ix_plan_features_feature_key", "plan_features", ["feature_key"])

    plan_features = sa.table(
        "plan_features",
        sa.column("id", sa.UUID()),
        sa.column("plan_code", sa.String()),
        sa.column("feature_key", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid.uuid4(),
            "plan_code": plan_code,
            "feature_key": feature_key,
            "enabled": enabled,
            "created_at": now,
        }
        for plan_code, feature_key, enabled in _MATRIX
    ]
    op.bulk_insert(plan_features, rows)


def downgrade() -> None:
    op.drop_index("ix_plan_features_feature_key", table_name="plan_features")
    op.drop_index("ix_plan_features_plan_code", table_name="plan_features")
    op.drop_table("plan_features")
