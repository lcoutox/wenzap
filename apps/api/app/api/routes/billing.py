"""Billing API endpoints (Stripe integration)."""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.workspace import Workspace
from app.services.auth import get_current_user_workspace
from app.services.stripe_service import StripeService
from app.services.stripe_webhook_handler import StripeWebhookHandler

router = APIRouter(prefix="/workspaces", tags=["billing"])

# Initialize Stripe service with API key from environment
stripe_api_key = os.getenv("STRIPE_API_KEY")
stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe_service = StripeService(api_key=stripe_api_key)
webhook_handler = StripeWebhookHandler(stripe_service)


class CheckoutSessionRequest(BaseModel):
    """Request to create a checkout session."""

    plan_id: str
    coupon_code: str | None = None


class CheckoutSessionResponse(BaseModel):
    """Response from checkout session creation."""

    checkout_url: str


class CouponValidationRequest(BaseModel):
    """Request to validate a coupon."""

    coupon_code: str
    plan_id: str


class CouponValidationResponse(BaseModel):
    """Response from coupon validation."""

    valid: bool
    code: str | None = None
    discount_type: str | None = None
    discount_value: float | None = None
    original_price_cents: int | None = None
    discounted_price_cents: int | None = None
    error: str | None = None


@router.post("/{workspace_id}/billing/checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(
    workspace_id: str,
    request: CheckoutSessionRequest,
    workspace: Annotated[Workspace, Depends(get_current_user_workspace)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a Stripe checkout session for subscription upgrade.

    Args:
        workspace_id: Workspace ID (from path, validated via auth)
        request: Checkout request with plan_id and optional coupon_code
        workspace: Authenticated workspace
        db: Database session

    Returns:
        Checkout session URL
    """
    if str(workspace.id) != workspace_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        # Fetch target plan
        plan = db.query(db.model.Plan).filter(
            db.model.Plan.id == request.plan_id
        ).first()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Create checkout session with optional coupon
        checkout_url = stripe_service.create_checkout_session(
            workspace=workspace,
            target_plan=plan,
            coupon_code=request.coupon_code,
            db=db,
        )

        stripe_service.log_sync_action(
            db=db,
            workspace_id=workspace.id,
            action="checkout_session_created",
            status="success",
            stripe_response={"checkout_url": checkout_url},
        )

        return CheckoutSessionResponse(checkout_url=checkout_url)

    except Exception as e:
        stripe_service.log_sync_action(
            db=db,
            workspace_id=workspace.id,
            action="checkout_session_failed",
            status="failed",
            error_message=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{workspace_id}/billing/portal-session")
def get_billing_portal_session(
    workspace_id: str,
    workspace: Annotated[Workspace, Depends(get_current_user_workspace)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Get a Stripe billing portal session for subscription management.

    Args:
        workspace_id: Workspace ID (from path)
        workspace: Authenticated workspace
        db: Database session

    Returns:
        Portal session URL
    """
    if str(workspace.id) != workspace_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        import stripe

        # Get workspace subscription and customer ID
        workspace_sub = db.query(db.model.WorkspaceSubscription).filter(
            db.model.WorkspaceSubscription.workspace_id == workspace.id
        ).first()

        if not workspace_sub or not workspace_sub.stripe_customer_id:
            raise HTTPException(
                status_code=400,
                detail="No active subscription found",
            )

        # Create billing portal session
        session = stripe.billing_portal.Session.create(
            customer=workspace_sub.stripe_customer_id,
            return_url="https://app.wenzap.com.br/dashboard/billing",
        )

        stripe_service.log_sync_action(
            db=db,
            workspace_id=workspace.id,
            action="portal_session_created",
            status="success",
            stripe_response={"portal_url": session.url},
        )

        return {"portal_url": session.url}

    except Exception as e:
        stripe_service.log_sync_action(
            db=db,
            workspace_id=workspace.id,
            action="portal_session_failed",
            status="failed",
            error_message=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{workspace_id}/billing/validate-coupon", response_model=CouponValidationResponse)
def validate_coupon(
    workspace_id: str,
    request: CouponValidationRequest,
    workspace: Annotated[Workspace, Depends(get_current_user_workspace)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Validate a coupon code and return discount details.

    Args:
        workspace_id: Workspace ID
        request: Validation request with coupon_code and plan_id
        workspace: Authenticated workspace
        db: Database session

    Returns:
        Validation result with discount details
    """
    if str(workspace.id) != workspace_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        # Fetch target plan
        plan = db.query(db.model.Plan).filter(
            db.model.Plan.id == request.plan_id
        ).first()

        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        # Validate coupon
        result = stripe_service.validate_coupon(
            coupon_code=request.coupon_code,
            target_plan=plan,
        )

        return CouponValidationResponse(**result)

    except Exception as e:
        return CouponValidationResponse(
            valid=False,
            error=str(e),
        )


@router.post("/webhooks/stripe")
async def handle_stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Handle Stripe webhook events.

    Args:
        request: HTTP request with webhook payload
        db: Database session

    Returns:
        Acknowledgment response
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    # Verify webhook signature
    event = stripe_service.verify_webhook_signature(
        payload=payload,
        sig_header=sig_header,
        webhook_secret=stripe_webhook_secret,
    )

    if not event:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Process event (with idempotency)
    try:
        webhook_handler.process_event(event, db)
        return {"status": "ok"}
    except Exception as e:
        # Log but still return 200 to prevent Stripe retry loops
        # The event is marked as processed, so re-processing is idempotent
        import logging

        logging.error(f"Webhook processing error: {e}", exc_info=True)
        return {"status": "ok"}
