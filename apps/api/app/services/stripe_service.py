"""
Stripe integration service for billing subscriptions, checkouts, and webhooks.

Handles:
- Customer management
- Checkout sessions
- Billing portal sessions
- Subscription cancellation
- Coupon validation
- Webhook signature verification
"""

import logging
import uuid
from datetime import datetime, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.plan import Plan
from app.models.stripe_sync_log import StripeSyncLog
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_subscription import WorkspaceSubscription

logger = logging.getLogger(__name__)


class StripeNotConfiguredError(RuntimeError):
    """Raised when a Stripe operation is attempted without required config."""


class StripeService:
    """Service for Stripe operations. One instance per request (see Depends(get_stripe_service))."""

    def __init__(self) -> None:
        stripe.api_key = settings.stripe_api_key

    def _require_configured(self) -> None:
        if not settings.stripe_api_key:
            raise StripeNotConfiguredError(
                "STRIPE_API_KEY is not set. Billing is not available in this environment."
            )

    def price_id_for_plan(self, plan_code: str) -> str:
        price_id = settings.stripe_price_by_plan_code.get(plan_code)
        if not price_id:
            raise ValueError(f"No Stripe price configured for plan '{plan_code}'")
        return price_id

    def plan_code_for_price_id(self, price_id: str) -> str | None:
        for code, pid in settings.stripe_price_by_plan_code.items():
            if pid == price_id:
                return code
        return None

    def create_customer(self, workspace: Workspace, db: Session) -> str:
        """Create a Stripe customer or return the existing customer_id."""
        self._require_configured()

        workspace_sub = db.scalar(
            select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace.id)
        )
        if workspace_sub and workspace_sub.stripe_customer_id:
            return workspace_sub.stripe_customer_id

        owner = db.scalar(select(User).where(User.id == workspace.owner_user_id))
        owner_email = owner.email if owner else None
        if not owner_email:
            raise ValueError(f"Workspace {workspace.id} has no resolvable owner email")

        customer = stripe.Customer.create(
            name=workspace.name,
            email=owner_email,
            metadata={"workspace_id": str(workspace.id)},
        )
        logger.info("Created Stripe customer %s for workspace %s", customer.id, workspace.id)
        return customer.id

    def create_checkout_session(
        self,
        workspace: Workspace,
        target_plan: Plan,
        db: Session,
        coupon_code: str | None = None,
    ) -> str:
        """Create a Stripe Checkout session for a subscription upgrade. Returns the checkout URL."""
        self._require_configured()

        customer_id = self.create_customer(workspace, db)
        price_id = self.price_id_for_plan(target_plan.code)

        session_params: dict = {
            "mode": "subscription",
            "customer": customer_id,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{settings.app_url}/dashboard/plan?checkout=success",
            "cancel_url": f"{settings.app_url}/dashboard/plan?checkout=cancelled",
            "metadata": {"workspace_id": str(workspace.id), "plan_code": target_plan.code},
            # Propagated onto the created Subscription object so webhook handlers
            # can resolve the workspace without a metadata round-trip.
            "subscription_data": {
                "metadata": {"workspace_id": str(workspace.id), "plan_code": target_plan.code}
            },
        }
        if coupon_code:
            session_params["discounts"] = [{"coupon": coupon_code}]
        else:
            session_params["allow_promotion_codes"] = True

        session = stripe.checkout.Session.create(**session_params)
        logger.info("Created checkout session %s for workspace %s", session.id, workspace.id)
        return session.url

    def create_portal_session(self, workspace: Workspace, db: Session) -> str:
        """Create a Stripe Billing Portal session. Returns the portal URL."""
        self._require_configured()

        workspace_sub = db.scalar(
            select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace.id)
        )
        if not workspace_sub or not workspace_sub.stripe_customer_id:
            raise ValueError("No Stripe customer found for this workspace")

        session = stripe.billing_portal.Session.create(
            customer=workspace_sub.stripe_customer_id,
            return_url=f"{settings.app_url}/dashboard/plan",
        )
        return session.url

    def cancel_subscription(self, workspace: Workspace, db: Session, reason: str | None = None) -> None:
        """Cancel a subscription at period end (graceful cancellation)."""
        self._require_configured()

        workspace_sub = db.scalar(
            select(WorkspaceSubscription).where(WorkspaceSubscription.workspace_id == workspace.id)
        )
        if not workspace_sub or not workspace_sub.stripe_subscription_id:
            raise ValueError("No active Stripe subscription found for this workspace")

        stripe.Subscription.modify(
            workspace_sub.stripe_subscription_id,
            cancel_at_period_end=True,
            metadata={"cancellation_reason": reason or "user_requested"},
        )
        logger.info("Marked subscription %s for cancellation", workspace_sub.stripe_subscription_id)

    def validate_coupon(self, coupon_code: str, target_plan: Plan) -> dict:
        """Validate a coupon code and return discount details for target_plan."""
        self._require_configured()

        try:
            coupon = stripe.Coupon.retrieve(coupon_code)
        except stripe.error.InvalidRequestError:
            return {"valid": False, "error": "Cupom não encontrado"}

        if not coupon.valid:
            return {"valid": False, "error": "Cupom inválido ou expirado"}

        if coupon.max_redemptions and coupon.times_redeemed >= coupon.max_redemptions:
            return {"valid": False, "error": "Cupom esgotado"}

        original_price = target_plan.monthly_price_cents
        if coupon.percent_off:
            discount_amount = round(original_price * coupon.percent_off / 100)
            discount_type = "percent"
            discount_value = coupon.percent_off
        elif coupon.amount_off:
            discount_amount = coupon.amount_off
            discount_type = "fixed"
            discount_value = coupon.amount_off / 100
        else:
            discount_amount = 0
            discount_type = "fixed"
            discount_value = 0

        discounted_price = max(0, original_price - discount_amount)

        return {
            "valid": True,
            "code": coupon_code,
            "discount_type": discount_type,
            "discount_value": discount_value,
            "original_price_cents": original_price,
            "discounted_price_cents": discounted_price,
            "expires_at": datetime.fromtimestamp(coupon.redeem_by, tz=timezone.utc).isoformat()
            if coupon.redeem_by
            else None,
        }

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> dict | None:
        """Verify a Stripe webhook signature and return the parsed event, or None if invalid."""
        if not settings.stripe_webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET is not set — rejecting webhook")
            return None
        try:
            return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.error("Invalid Stripe webhook: %s", e)
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
        """Log a Stripe sync action for audit trail. Commits independently of the caller's transaction."""
        log = StripeSyncLog(
            workspace_id=workspace_id,
            action=action,
            status=status,
            stripe_response=stripe_response,
            error_message=error_message,
        )
        db.add(log)
        db.commit()


def get_stripe_service() -> StripeService:
    """FastAPI dependency — one StripeService per request."""
    return StripeService()
