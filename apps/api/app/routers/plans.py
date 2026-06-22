from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_workspace
from app.database import get_db
from app.models.workspace import Workspace
from app.schemas.plan import PlanOut, SubscriptionOut, UsageOut
from app.services.plan_service import (
    get_workspace_subscription,
    get_workspace_usage,
    list_plans,
)

router = APIRouter()


@router.get("/plans", response_model=list[PlanOut])
def get_plans(db: Session = Depends(get_db)) -> list[PlanOut]:
    return list_plans(db)


@router.get("/workspaces/current/plan", response_model=SubscriptionOut)
def get_current_plan(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    return get_workspace_subscription(db, current_workspace.id)


@router.get("/workspaces/current/usage", response_model=UsageOut)
def get_current_usage(
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> UsageOut:
    return get_workspace_usage(db, current_workspace.id)
