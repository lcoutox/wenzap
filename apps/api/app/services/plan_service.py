import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.catalog_item import CatalogItem
from app.models.channel import Channel
from app.models.knowledge_base import KnowledgeBase
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


def _count_resources(db: Session, workspace_id: uuid.UUID) -> dict:
    agents = db.scalar(
        select(func.count()).where(
            Agent.workspace_id == workspace_id,
            Agent.status != "archived",
        )
    ) or 0
    kbs = db.scalar(
        select(func.count()).where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.status != "archived",
        )
    ) or 0
    catalog = db.scalar(
        select(func.count()).where(
            CatalogItem.workspace_id == workspace_id,
            CatalogItem.status != "archived",
        )
    ) or 0
    channels = db.scalar(
        select(func.count()).where(
            Channel.workspace_id == workspace_id,
            Channel.status != "archived",
        )
    ) or 0
    return {
        "agents_count": agents,
        "knowledge_bases_count": kbs,
        "catalog_items_count": catalog,
        "channels_count": channels,
    }


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

    resources = _count_resources(db, workspace_id)

    if counter is None:
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
            **resources,
        )

    return UsageOut(
        ai_credits_used=counter.ai_credits_used,
        conversations_count=counter.conversations_count,
        messages_count=counter.messages_count,
        period_start=counter.period_start,
        period_end=counter.period_end,
        **resources,
    )


def get_or_create_usage_counter(db: Session, workspace_id: uuid.UUID) -> UsageCounter:
    """Return the active UsageCounter for the current month, creating it on-demand."""
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
    if counter is not None:
        return counter

    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        next_month = period_start.replace(year=period_start.year + 1, month=1, day=1)
    else:
        next_month = period_start.replace(month=period_start.month + 1, day=1)
    period_end = next_month - timedelta(seconds=1)

    try:
        sp = db.begin_nested()
        counter = UsageCounter(
            workspace_id=workspace_id,
            period_start=period_start,
            period_end=period_end,
            ai_credits_used=0,
            conversations_count=0,
            messages_count=0,
        )
        db.add(counter)
        db.flush()
        sp.commit()
    except (IntegrityError, Exception):
        sp.rollback()
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
            raise

    return counter


def count_new_conversation(db: Session, workspace_id: uuid.UUID) -> None:
    """Increment conversations_count as an operational metric. Does not enforce any limit."""
    get_or_create_usage_counter(db, workspace_id)

    now = datetime.now(timezone.utc)
    db.execute(
        update(UsageCounter)
        .where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.period_start <= now,
            UsageCounter.period_end >= now,
        )
        .values(conversations_count=UsageCounter.conversations_count + 1)
    )


# Keep old name as alias so any external callers still work during migration.
check_and_count_new_conversation = count_new_conversation
