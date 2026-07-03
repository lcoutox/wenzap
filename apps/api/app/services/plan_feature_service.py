"""
Feature gate helpers — DB-backed (Plans.5).

Feature gates are stored in the `plan_features` table and queried per request.
Default deny: an absent row is treated as disabled.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.plan_feature import PlanFeature
from app.models.workspace_subscription import WorkspaceSubscription

# ---------------------------------------------------------------------------
# Public constants — canonical set of feature keys
# ---------------------------------------------------------------------------

FEATURE_KEYS: frozenset[str] = frozenset(
    [
        # Channel types
        "web_widget",
        "api",
        "whatsapp",
        "instagram",
        "telegram",
        "slack",
        # General features
        "knowledge_base",
        "catalog",
        "inbox",
        "playground",
        "pipelines",
        "pipeline_automations",
        "multiple_knowledge_bases",
        "whatsapp_channel",
        "api_access",
        "http_tools",
        "follow_up",
        "webhooks",
        "custom_model",
        "analytics",
        "external_integrations",
        "remove_powered_by",
        "premium_models",
    ]
)

# ---------------------------------------------------------------------------
# Plan helpers
# ---------------------------------------------------------------------------


def get_workspace_plan_code(db: Session, workspace_id: uuid.UUID) -> str:
    sub = db.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id,
            WorkspaceSubscription.status == "active",
        )
    )
    if sub is None:
        return "starter"
    plan = db.scalar(select(Plan).where(Plan.id == sub.plan_id))
    return plan.code if plan else "starter"


# ---------------------------------------------------------------------------
# Feature gate — DB-backed, default deny
# ---------------------------------------------------------------------------


def plan_allows_feature(db: Session, plan_code: str, feature_key: str) -> bool:
    """Return True only if plan_features has an enabled row for (plan_code, feature_key)."""
    row = db.scalar(
        select(PlanFeature).where(
            PlanFeature.plan_code == plan_code,
            PlanFeature.feature_key == feature_key,
        )
    )
    if row is None:
        return False
    return row.enabled


def plan_allows_channel_type(db: Session, plan_code: str, channel_type: str) -> bool:
    """Channel type checks reuse plan_allows_feature (channel_type == feature_key)."""
    return plan_allows_feature(db, plan_code, channel_type)


def workspace_allows_feature(
    db: Session, workspace_id: uuid.UUID, feature_key: str
) -> bool:
    plan_code = get_workspace_plan_code(db, workspace_id)
    return plan_allows_feature(db, plan_code, feature_key)


def workspace_allows_channel_type(
    db: Session, workspace_id: uuid.UUID, channel_type: str
) -> bool:
    plan_code = get_workspace_plan_code(db, workspace_id)
    return plan_allows_channel_type(db, plan_code, channel_type)


# ---------------------------------------------------------------------------
# Enforcement helpers
# ---------------------------------------------------------------------------


def check_channel_type_or_402(
    db: Session, workspace_id: uuid.UUID, channel_type: str
) -> None:
    if not workspace_allows_channel_type(db, workspace_id, channel_type):
        plan_code = get_workspace_plan_code(db, workspace_id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Channel type '{channel_type}' is not available on the "
                f"{plan_code.title()} plan. "
                "Upgrade your plan to enable this channel."
            ),
        )


def check_users_limit(db: Session, workspace_id: uuid.UUID) -> None:
    """Raises HTTP 402 if the workspace has reached its users_limit."""
    from sqlalchemy import func  # noqa: PLC0415

    from app.enums import MemberStatus  # noqa: PLC0415
    from app.models.workspace_member import WorkspaceMember  # noqa: PLC0415

    plan_code = get_workspace_plan_code(db, workspace_id)
    plan = db.scalar(select(Plan).where(Plan.code == plan_code))
    if plan is None or plan.users_limit <= 0:
        return

    active_count = (
        db.scalar(
            select(func.count()).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.status == MemberStatus.active,
            )
        )
        or 0
    )

    if active_count >= plan.users_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Member limit reached for your plan ({plan.users_limit} user(s) allowed). "
                "Upgrade your plan to invite more members."
            ),
        )
