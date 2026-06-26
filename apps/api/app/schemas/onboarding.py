"""
Pydantic schemas for the workspace onboarding profile — Phase Growth.1-A.

Enum values are stored as plain strings in the DB for readability and
forward-compatibility. Pydantic validates them via Literal unions.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Enum literals ──────────────────────────────────────────────────────────────

MainObjective = Literal[
    "customer_support",
    "sales_qualification",
    "technical_support",
    "scheduling",
    "collections_followup",
    "other",
]

ExpectedMonthlyConversations = Literal[
    "up_to_100",
    "100_to_500",
    "500_to_2000",
    "2000_plus",
]

AiExperience = Literal[
    "never_used",
    "tested_tools",
    "using_in_production",
]

CompanyIndustry = Literal[
    "clinic_health",
    "real_estate",
    "automotive",
    "ecommerce",
    "professional_services",
    "education",
    "saas_tech",
    "retail",
    "other",
]

Role = Literal[
    "owner_founder",
    "partner_director",
    "sales_manager",
    "support_manager",
    "marketing",
    "sales",
    "operations",
    "developer_it",
    "other",
]

HeardFrom = Literal[
    "google",
    "instagram",
    "youtube",
    "referral",
    "chatgpt",
    "community",
    "other",
]


# ── Input schema ───────────────────────────────────────────────────────────────


class OnboardingProfileCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # Personal
    full_name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=8, max_length=50)

    # Intent
    main_objective: MainObjective
    expected_monthly_conversations: ExpectedMonthlyConversations
    ai_experience: AiExperience

    # Company
    company_name: str = Field(min_length=2, max_length=200)
    company_industry: CompanyIndustry
    company_website: str | None = Field(default=None, max_length=500)
    role: Role

    # Origin & consent
    heard_from: HeardFrom
    contact_consent: bool = False

    @field_validator("company_website", mode="before")
    @classmethod
    def normalize_website(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        return v

    @field_validator("company_website", mode="after")
    @classmethod
    def validate_website_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("company_website must start with http:// or https://")
        return v


# ── Output schemas ─────────────────────────────────────────────────────────────


class OnboardingProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID

    full_name: str
    phone: str

    main_objective: str
    expected_monthly_conversations: str
    ai_experience: str

    company_name: str
    company_industry: str
    company_website: str | None
    role: str

    heard_from: str
    contact_consent: bool

    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OnboardingStatusOut(BaseModel):
    completed: bool
    profile: OnboardingProfileOut | None
