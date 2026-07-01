import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import SubscriptionStatus


class PlanOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    monthly_price_cents: int
    currency: str
    agents_limit: int
    knowledge_bases_limit: int
    users_limit: int
    pipelines_limit: int
    integrations_limit: int
    catalog_items_limit: int
    channels_limit: int
    monthly_ai_credits: int
    monthly_conversations: int

    model_config = {"from_attributes": True}


class SubscriptionOut(BaseModel):
    plan: PlanOut
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime

    model_config = {"from_attributes": True}


class UsageOut(BaseModel):
    # Metered counters (reset monthly)
    ai_credits_used: int
    conversations_count: int
    messages_count: int
    # Resource snapshots (current count, not metered)
    agents_count: int = 0
    knowledge_bases_count: int = 0
    catalog_items_count: int = 0
    channels_count: int = 0
    period_start: datetime
    period_end: datetime

    model_config = {"from_attributes": True}
