"""
Stripe integration service for billing subscriptions, checkouts, and webhooks.

Handles:
- Customer management
- Checkout sessions
- Subscription lifecycle
- Webhook verification and processing
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone

import stripe
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.stripe_event import StripeEvent
from app.models.stripe_sync_log import StripeSyncLog
from app.models.workspace_subscription import WorkspaceSubscription
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe operations."""

    def __init__(self, api_key: str):
        """Initialize Stripe service with API key."""
        stripe.api_key = api_key

    def create_customer(self, workspace: Workspace, db: Session) -> str:
        """
        Create a Stripe customer or return existing customer_id.

        Args:
            workspace: Workspace instance
            db: Database session

        Returns:
            Stripe customer ID (cus_...)
        """
        workspace_sub = db.query(WorkspaceSubscription).filter(
            WorkspaceSubscription.workspace_id == workspace.id
        ).first()

        if workspace_sub and workspace_sub.stripe_customer_id:
            return workspace_sub.stripe_customer_id

        try:
            customer = stripe.Customer.create(
                name=workspace.name,
                email=workspace.admin_email or "noreply@wenzap.com.br",
                metadata={"workspace_id": str(workspace.id)},
            )
            logger.info(f"Created Stripe customer {customer.id} for workspace {workspace.id}")
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise

    def create_checkout_session(
        self,
        workspace: Workspace,
        target_plan: Plan,
        coupon_code: str | None = None,
        db: Session | None = None,
    ) -> str:
        """
        Create a Stripe checkout session for subscription upgrade.

        Args:
            workspace: Workspace instance
            target_plan: Target Plan to upgrade to
            coupon_code: Optional coupon code for discount
            db: Database session (required to create customer if needed)

        Returns:
            Stripe checkout session URL
        """
        if not db:
            raise ValueError("Database session required")

        customer_id = self.create_customer(workspace, db)

        # Map plan code to Stripe price ID
        price_id = self._plan_to_price_id(target_plan.code)

        try:
            session_params = {
                "payment_method_types": ["card"],
                "mode": "subscription",
                "customer": customer_id,
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                "success_url": "https://app.wenzap.com.br/dashboard/billing?success=true",
                "cancel_url": "https://app.wenzap.com.br/dashboard?cancelled=true",
                "metadata": {
                    "workspace_id": str(workspace.id),
                    "plan_code": target_plan.code,
                },
            }

            # Add coupon if provided
            if coupon_code:
                session_params["discounts"] = [{"coupon": coupon_code}]

            session = stripe.checkout.Session.create(**session_params)
            logger.info(f"Created checkout session {session.id} for workspace {workspace.id}")
            return session.url

        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise

    def cancel_subscription(self, workspace: Workspace, db: Session, reason: str | None = None) -> None:
        """
        Cancel subscription at period end (graceful cancellation).

        Args:
            workspace: Workspace instance
            db: Database session
            reason: Optional cancellation reason
        """
        workspace_sub = db.query(WorkspaceSubscription).filter(
            WorkspaceSubscription.workspace_id == workspace.id
        ).first()

        if not workspace_sub or not workspace_sub.stripe_subscription_id:
            logger.warning(f"No subscription found for workspace {workspace.id}")
            return

        try:
            stripe.Subscription.modify(
                workspace_sub.stripe_subscription_id,
                cancel_at_period_end=True,
                metadata={"cancellation_reason": reason or "user_requested"},
            )
            logger.info(f"Marked subscription {workspace_sub.stripe_subscription_id} for cancellation")
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise

    def validate_coupon(self, coupon_code: str, target_plan: Plan) -> dict:
        """
        Validate a coupon code and return discount details.

        Args:
            coupon_code: Coupon code to validate
            target_plan: Plan to apply coupon to

        Returns:
            Dictionary with coupon details and discounted price
        """
        try:
            coupon = stripe.Coupon.retrieve(coupon_code)

            # Validation checks
            if not coupon.valid:
                return {"valid": False, "error": "Coupon is invalid"}

            if coupon.redeem_by and coupon.redeem_by < datetime.now(timezone.utc).timestamp():
                return {"valid": False, "error": "Coupon expired"}

            if coupon.max_redemptions and coupon.times_redeemed >= coupon.max_redemptions:
                return {"valid": False, "error": "Coupon exhausted"}

            # Calculate discounted price
            original_price = target_plan.monthly_price_cents
            discount_amount = 0

            if coupon.percent_off:
                discount_amount = int(original_price * coupon.percent_off / 100)
            elif coupon.amount_off:
                discount_amount = coupon.amount_off

            discounted_price = max(0, original_price - discount_amount)

            return {
                "valid": True,
                "code": coupon_code,
                "discount_type": "percent" if coupon.percent_off else "fixed",
                "discount_value": coupon.percent_off or (coupon.amount_off / 100),
                "original_price_cents": original_price,
                "discounted_price_cents": discounted_price,
                "expires_at": datetime.fromtimestamp(coupon.redeem_by, tz=timezone.utc).isoformat()
                if coupon.redeem_by
                else None,
            }

        except stripe.error.InvalidRequestError:
            return {"valid": False, "error": "Coupon not found"}
        except Exception as e:
            logger.error(f"Coupon validation error: {e}")
            return {"valid": False, "error": str(e)}

    def verify_webhook_signature(self, payload: bytes, sig_header: str, webhook_secret: str) -> dict | None:
        """
        Verify Stripe webhook signature and return event data.

        Args:
            payload: Raw webhook payload
            sig_header: Stripe signature header
            webhook_secret: Webhook secret from Stripe

        Returns:
            Event dict if valid, None if invalid
        """
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            return event
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            return None
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            return None

    def log_sync_action(
        self,
        db: Session,
        workspace_id: uuid.UUID | None,
        action: str,
        status: str,
        stripe_response: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Log a Stripe sync action for audit trail.

        Args:
            db: Database session
            workspace_id: Workspace ID (if applicable)
            action: Action type (create, cancel, update, etc.)
            status: Status (success, failed, pending)
            stripe_response: Stripe API response (if successful)
            error_message: Error message (if failed)
        """
        log = StripeSyncLog(
            workspace_id=workspace_id,
            action=action,
            status=status,
            stripe_response=stripe_response,
            error_message=error_message,
        )
        db.add(log)
        db.commit()
        logger.info(f"Logged Stripe sync: action={action}, status={status}, workspace={workspace_id}")

    @staticmethod
    def _plan_to_price_id(plan_code: str) -> str:
        """
        Map Wenzap plan code to Stripe price ID.

        Args:
            plan_code: Wenzap plan code (e.g., "growth", "scale")

        Returns:
            Stripe price ID
        """
        price_map = {
            "growth": "price_growth_monthly_brl",
            "scale": "price_scale_monthly_brl",
        }
        price_id = price_map.get(plan_code)
        if not price_id:
            raise ValueError(f"Unknown plan code: {plan_code}")
        return price_id
