"""
Feature gate helpers (Option B — hardcoded).

No DB round-trip for flag lookups; plan code is fetched once and gates are
evaluated against in-memory dictionaries.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription

# ---------------------------------------------------------------------------
# Tier order
# ---------------------------------------------------------------------------

_PLAN_TIER: dict[str, int] = {
    "starter": 1,
    "growth": 2,
    "scale": 3,
    "enterprise": 4,
}

# ---------------------------------------------------------------------------
# Channel type allowlist per plan
# ---------------------------------------------------------------------------

_PLAN_CHANNEL_TYPES: dict[str, set[str]] = {
    "starter": {"web_widget", "api"},
    "growth": {"web_widget", "api", "whatsapp"},
    "scale": {"web_widget", "api", "whatsapp", "instagram", "telegram"},
    "enterprise": {"web_widget", "api", "whatsapp", "instagram", "telegram", "slack"},
}

# ---------------------------------------------------------------------------
# Feature → minimum plan required
# ---------------------------------------------------------------------------

_FEATURE_MIN_PLAN: dict[str, str] = {
    # Growth+
    "whatsapp_channel":         "growth",
    "pipelines":                "growth",
    "integrations":             "growth",
    "catalog":                  "growth",
    "multiple_knowledge_bases": "growth",
    "api_access":               "growth",
    # Scale+ (not available on Growth)
    "remove_powered_by":        "scale",
    "http_tools":               "scale",
    "follow_up":                "scale",
    "webhooks":                 "scale",
    "custom_model":             "scale",
    "analytics":                "scale",
}


# ---------------------------------------------------------------------------
# Helpers
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


def plan_tier(plan_code: str) -> int:
    return _PLAN_TIER.get(plan_code, 1)


def plan_allows_channel_type(plan_code: str, channel_type: str) -> bool:
    allowed = _PLAN_CHANNEL_TYPES.get(plan_code)
    if allowed is None:
        return True  # Unknown/custom plan codes are not restricted
    return channel_type in allowed


def plan_allows_feature(plan_code: str, feature: str) -> bool:
    min_plan = _FEATURE_MIN_PLAN.get(feature)
    if min_plan is None:
        return True
    return plan_tier(plan_code) >= plan_tier(min_plan)


def check_channel_type_or_402(
    db: Session, workspace_id: uuid.UUID, channel_type: str
) -> None:
    plan_code = get_workspace_plan_code(db, workspace_id)
    if not plan_allows_channel_type(plan_code, channel_type):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Channel type '{channel_type}' is not available on the "
                f"{plan_code.title()} plan. "
                "Upgrade your plan to enable this channel."
            ),
        )


def check_users_limit(db: Session, workspace_id: uuid.UUID) -> None:
    """Raises HTTP 402 if the workspace has reached its users_limit.

    Call this from the invite / member-add flow before creating a new member.
    No invite endpoint exists yet — placeholder for future implementation.
    """
    from sqlalchemy import func  # noqa: PLC0415

    from app.enums import MemberStatus  # noqa: PLC0415
    from app.models.workspace_member import WorkspaceMember  # noqa: PLC0415

    plan_code = get_workspace_plan_code(db, workspace_id)
    plan = db.scalar(select(Plan).where(Plan.code == plan_code))
    if plan is None or plan.users_limit <= 0:
        return

    active_count = db.scalar(
        select(func.count()).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == MemberStatus.active,
        )
    ) or 0

    if active_count >= plan.users_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Member limit reached for your plan ({plan.users_limit} user(s) allowed). "
                "Upgrade your plan to invite more members."
            ),
        )
