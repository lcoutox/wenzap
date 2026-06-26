"""
Onboarding service — Phase Growth.1-A.

Handles creation, update, and status query for workspace_onboarding_profiles.

Isolation: all operations are scoped to the current workspace derived from
the authenticated user context. workspace_id and user_id are never accepted
from request bodies.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace_onboarding_profile import WorkspaceOnboardingProfile
from app.schemas.onboarding import OnboardingProfileCreate, OnboardingStatusOut


def get_onboarding_status(
    db: Session,
    workspace_id: uuid.UUID,
) -> OnboardingStatusOut:
    """
    Return the current onboarding status for the workspace.

    Returns completed=False and profile=None if no profile exists yet.
    Returns completed=True if completed_at is set.
    """
    profile = db.scalar(
        select(WorkspaceOnboardingProfile).where(
            WorkspaceOnboardingProfile.workspace_id == workspace_id
        )
    )
    if profile is None:
        return OnboardingStatusOut(completed=False, profile=None)

    completed = profile.completed_at is not None
    return OnboardingStatusOut(completed=completed, profile=profile)


def submit_onboarding_profile(
    db: Session,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: OnboardingProfileCreate,
) -> OnboardingStatusOut:
    """
    Create or update the onboarding profile for the workspace, and mark it complete.

    If a profile already exists and completed_at is already set, the data is
    updated but completed_at is preserved (not cleared or reset).

    workspace_id and user_id come from authenticated context, never from input.
    """
    now = datetime.now(timezone.utc)

    profile = db.scalar(
        select(WorkspaceOnboardingProfile).where(
            WorkspaceOnboardingProfile.workspace_id == workspace_id
        )
    )

    if profile is None:
        profile = WorkspaceOnboardingProfile(
            workspace_id=workspace_id,
            user_id=user_id,
            completed_at=now,
        )
        db.add(profile)
    else:
        if profile.completed_at is None:
            profile.completed_at = now
        profile.updated_at = now

    # Apply all submitted fields.
    profile.full_name = data.full_name
    profile.phone = data.phone
    profile.main_objective = data.main_objective
    profile.expected_monthly_conversations = data.expected_monthly_conversations
    profile.ai_experience = data.ai_experience
    profile.company_name = data.company_name
    profile.company_industry = data.company_industry
    profile.company_website = data.company_website
    profile.role = data.role
    profile.heard_from = data.heard_from
    profile.contact_consent = data.contact_consent

    db.commit()
    db.refresh(profile)

    return OnboardingStatusOut(completed=True, profile=profile)
