import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.plan import SubscriptionOut, UsageOut


def list_plans(db: Session) -> list[Plan]:
    return list(db.scalars(select(Plan).where(Plan.is_active == True)).all())  # noqa: E712


def get_workspace_subscription(db: Session, workspace_id: uuid.UUID) -> SubscriptionOut:
    sub = db.scalar(
        select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace_id)
    )
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No subscription found")

    plan = db.scalar(select(Plan).where(Plan.id == sub.plan_id))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    return SubscriptionOut(
        plan=plan,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
    )


def get_workspace_usage(db: Session, workspace_id: uuid.UUID) -> UsageOut:
    now = datetime.now(timezone.utc)
    counter = db.scalar(
        select(UsageCounter)
        .where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.period_start <= now,
            UsageCounter.period_end >= now,
        )
        .order_by(UsageCounter.period_start.desc())
    )

    if counter is None:
        # Return zeroed counter when no usage exists yet
        sub = db.scalar(
            select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace_id)
        )
        period_start = sub.current_period_start if sub else now
        period_end = sub.current_period_end if sub else now
        return UsageOut(
            ai_credits_used=0,
            conversations_count=0,
            messages_count=0,
            period_start=period_start,
            period_end=period_end,
        )

    return UsageOut(
        ai_credits_used=counter.ai_credits_used,
        conversations_count=counter.conversations_count,
        messages_count=counter.messages_count,
        period_start=counter.period_start,
        period_end=counter.period_end,
    )
