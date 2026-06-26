"""
Onboarding endpoints — Phase Growth.1-A.

GET  /onboarding   — return workspace onboarding status
POST /onboarding   — submit onboarding profile and mark complete

Workspace context comes from the authenticated user session, not from the URL.
Any active workspace member can complete onboarding.

Future consideration: when multi-member invites are introduced, onboarding
completion may need to be restricted to owner/admin role.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.onboarding import OnboardingProfileCreate, OnboardingStatusOut
from app.services.onboarding_service import get_onboarding_status, submit_onboarding_profile

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("", response_model=OnboardingStatusOut)
def get_onboarding(
    current_workspace: Workspace = Depends(get_current_workspace),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatusOut:
    return get_onboarding_status(db, current_workspace.id)


@router.post("", response_model=OnboardingStatusOut, status_code=200)
def post_onboarding(
    data: OnboardingProfileCreate,
    current_workspace: Workspace = Depends(get_current_workspace),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatusOut:
    return submit_onboarding_profile(db, current_workspace.id, current_user.id, data)
