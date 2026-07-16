import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import MemberRole
from app.models.plan import Plan
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.billing import (
    CancelSubscriptionRequest,
    CheckoutSessionOut,
    CheckoutSessionRequest,
    PortalSessionOut,
    ValidateCouponOut,
    ValidateCouponRequest,
)
from app.services.stripe_service import StripeNotConfiguredError, StripeService, get_stripe_service
from app.services.workspace_service import get_current_member_role

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces/current/billing",
    tags=["billing"],
    dependencies=[Depends(get_verified_user)],
)


def _require_billing_manager(db: Session, workspace: Workspace, user: User) -> None:
    """Only owner/admin can manage billing — mirrors update_workspace's guard."""
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in (MemberRole.owner, MemberRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissões insuficientes.")


def _get_plan_or_404(db: Session, plan_code: str) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.code == plan_code, Plan.is_active.is_(True)))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado.")
    return plan


@router.post("/checkout-session", response_model=CheckoutSessionOut)
def create_checkout_session(
    body: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> CheckoutSessionOut:
    _require_billing_manager(db, current_workspace, current_user)
    plan = _get_plan_or_404(db, body.plan_code)

    try:
        checkout_url = stripe_service.create_checkout_session(
            workspace=current_workspace,
            target_plan=plan,
            db=db,
            coupon_code=body.coupon_code,
        )
    except StripeNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        stripe_service.log_sync_action(
            db,
            workspace_id=current_workspace.id,
            action="checkout_session_failed",
            status="failed",
            error_message=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi possível iniciar o checkout")

    return CheckoutSessionOut(checkout_url=checkout_url)


@router.get("/portal-session", response_model=PortalSessionOut)
def get_portal_session(
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> PortalSessionOut:
    _require_billing_manager(db, current_workspace, current_user)

    try:
        portal_url = stripe_service.create_portal_session(current_workspace, db)
    except StripeNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return PortalSessionOut(portal_url=portal_url)


@router.post("/validate-coupon", response_model=ValidateCouponOut)
def validate_coupon(
    body: ValidateCouponRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> ValidateCouponOut:
    _require_billing_manager(db, current_workspace, current_user)
    plan = _get_plan_or_404(db, body.plan_code)

    try:
        result = stripe_service.validate_coupon(body.coupon_code, plan)
    except StripeNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    return ValidateCouponOut(**result)


@router.post("/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_subscription(
    body: CancelSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    stripe_service: StripeService = Depends(get_stripe_service),
) -> None:
    _require_billing_manager(db, current_workspace, current_user)

    try:
        stripe_service.cancel_subscription(current_workspace, db, reason=body.reason)
    except StripeNotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
