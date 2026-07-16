"""
Stripe webhook event handler for subscription lifecycle management.

Processes:
- Subscription creation/updates/cancellations
- Invoice payment success/failure
- Idempotent processing via stripe_event_id
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.stripe_event import StripeEvent
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.stripe_service import StripeService

logger = logging.getLogger(__name__)


class StripeWebhookHandler:
    """Handler for processing Stripe webhook events."""

    def __init__(self, stripe_service: StripeService):
        """Initialize webhook handler with Stripe service."""
        self.stripe_service = stripe_service

    def process_event(self, event: dict, db: Session) -> bool:
        """
        Process a Stripe webhook event with idempotency.

        Args:
            event: Stripe event dict (from verify_webhook_signature)
            db: Database session

        Returns:
            True if processed successfully, False if already processed
        """
        event_id = event.get("id")
        event_type = event.get("type")
        data = event.get("data", {})
        obj = data.get("object", {})

        # Check if event already processed (idempotency)
        existing = db.query(StripeEvent).filter(
            StripeEvent.stripe_event_id == event_id
        ).first()

        if existing and existing.processed_at:
            logger.info(f"Event {event_id} already processed, skipping")
            return False

        try:
            # Mark as processing (create if doesn't exist)
            if not existing:
                stripe_event = StripeEvent(
                    stripe_event_id=event_id,
                    event_type=event_type,
                    workspace_id=self._extract_workspace_id(obj),
                    payload=obj,
                )
                db.add(stripe_event)
                db.flush()
            else:
                stripe_event = existing

            # Route to specific handler
            handler_method = getattr(self, f"handle_{event_type.replace('.', '_')}", None)
            if handler_method:
                handler_method(obj, db)
                stripe_event.processed_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Processed event {event_id} ({event_type})")
                return True
            else:
                logger.warning(f"No handler for event type: {event_type}")
                return False

        except Exception as e:
            db.rollback()
            logger.error(f"Error processing event {event_id}: {e}", exc_info=True)
            self.stripe_service.log_sync_action(
                db,
                workspace_id=self._extract_workspace_id(obj),
                action="webhook_process",
                status="failed",
                error_message=str(e),
            )
            raise

    def handle_customer_subscription_created(self, subscription: dict, db: Session) -> None:
        """Handle customer.subscription.created event."""
        workspace_id = self._extract_workspace_id(subscription)
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        plan_id = self._extract_plan_id_from_subscription(subscription)

        if not workspace_id:
            logger.warning("Subscription created without workspace_id metadata")
            return

        # Find or create workspace subscription
        workspace_sub = db.query(WorkspaceSubscription).filter(
            WorkspaceSubscription.workspace_id == workspace_id
        ).first()

        if not workspace_sub:
            raise ValueError(f"No workspace subscription found for {workspace_id}")

        # Update with Stripe IDs
        workspace_sub.stripe_subscription_id = subscription_id
        workspace_sub.stripe_customer_id = customer_id
        workspace_sub.status = "active"
        workspace_sub.auto_renew = True
        workspace_sub.cancel_at_period_end = False

        # Update period dates
        current_period_start = subscription.get("current_period_start")
        current_period_end = subscription.get("current_period_end")

        if current_period_start:
            workspace_sub.period_start = datetime.fromtimestamp(
                current_period_start, tz=timezone.utc
            )
        if current_period_end:
            workspace_sub.period_end = datetime.fromtimestamp(
                current_period_end, tz=timezone.utc
            )

        db.commit()
        logger.info(
            f"Created subscription {subscription_id} for workspace {workspace_id}"
        )
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_id,
            action="create",
            status="success",
            stripe_response={"subscription_id": subscription_id},
        )

    def handle_customer_subscription_updated(self, subscription: dict, db: Session) -> None:
        """Handle customer.subscription.updated event."""
        subscription_id = subscription.get("id")
        workspace_id = self._extract_workspace_id(subscription)

        if not workspace_id:
            logger.warning(f"Subscription {subscription_id} updated without workspace_id")
            return

        workspace_sub = db.query(WorkspaceSubscription).filter(
            WorkspaceSubscription.workspace_id == workspace_id
        ).first()

        if not workspace_sub:
            logger.warning(f"No workspace subscription for update event: {workspace_id}")
            return

        # Update cancellation status if changed
        cancel_at_period_end = subscription.get("cancel_at_period_end", False)
        if cancel_at_period_end:
            workspace_sub.cancel_at_period_end = True
            workspace_sub.status = "cancelling"

        # Update period dates
        current_period_end = subscription.get("current_period_end")
        if current_period_end:
            workspace_sub.period_end = datetime.fromtimestamp(
                current_period_end, tz=timezone.utc
            )

        db.commit()
        logger.info(f"Updated subscription {subscription_id} for workspace {workspace_id}")
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_id,
            action="update",
            status="success",
            stripe_response={"subscription_id": subscription_id},
        )

    def handle_customer_subscription_deleted(self, subscription: dict, db: Session) -> None:
        """Handle customer.subscription.deleted event."""
        subscription_id = subscription.get("id")
        workspace_id = self._extract_workspace_id(subscription)

        if not workspace_id:
            logger.warning(f"Subscription {subscription_id} deleted without workspace_id")
            return

        workspace_sub = db.query(WorkspaceSubscription).filter(
            WorkspaceSubscription.workspace_id == workspace_id
        ).first()

        if not workspace_sub:
            logger.warning(f"No workspace subscription for deletion: {workspace_id}")
            return

        # Mark as cancelled/downgraded
        workspace_sub.status = "inactive"
        workspace_sub.auto_renew = False
        workspace_sub.cancelled_at = datetime.now(timezone.utc)
        workspace_sub.cancellation_reason = subscription.get("cancellation_details", {}).get(
            "reason", "cancelled_by_stripe"
        )

        db.commit()
        logger.info(f"Cancelled subscription {subscription_id} for workspace {workspace_id}")
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_id,
            action="cancel",
            status="success",
            stripe_response={"subscription_id": subscription_id},
        )

    def handle_invoice_payment_succeeded(self, invoice: dict, db: Session) -> None:
        """Handle invoice.payment_succeeded event."""
        invoice_id = invoice.get("id")
        customer_id = invoice.get("customer")
        workspace_id = self._extract_workspace_id(invoice)

        logger.info(f"Invoice {invoice_id} paid for customer {customer_id}")

        if workspace_id:
            self.stripe_service.log_sync_action(
                db,
                workspace_id=workspace_id,
                action="payment_succeeded",
                status="success",
                stripe_response={"invoice_id": invoice_id, "amount": invoice.get("total")},
            )

    def handle_invoice_payment_failed(self, invoice: dict, db: Session) -> None:
        """Handle invoice.payment_failed event."""
        invoice_id = invoice.get("id")
        customer_id = invoice.get("customer")
        workspace_id = self._extract_workspace_id(invoice)

        logger.error(f"Invoice {invoice_id} payment failed for customer {customer_id}")

        if workspace_id:
            self.stripe_service.log_sync_action(
                db,
                workspace_id=workspace_id,
                action="payment_failed",
                status="failed",
                error_message=f"Invoice {invoice_id} payment failed",
            )

    @staticmethod
    def _extract_workspace_id(stripe_object: dict) -> str | None:
        """Extract workspace_id from Stripe object metadata."""
        metadata = stripe_object.get("metadata", {})
        return metadata.get("workspace_id")

    @staticmethod
    def _extract_plan_id_from_subscription(subscription: dict) -> str | None:
        """Extract plan_id from Stripe subscription items."""
        items = subscription.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            # Map Stripe price ID back to plan code (inverse of _plan_to_price_id)
            price_to_plan = {
                "price_growth_monthly_brl": "growth",
                "price_scale_monthly_brl": "scale",
            }
            return price_to_plan.get(price_id)
        return None
