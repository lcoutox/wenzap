"""
Stripe webhook event handler for subscription lifecycle management.

Every workspace already has exactly one WorkspaceSubscription row (created at
signup on the starter plan — see auth.py _provision_workspace), so handlers
here only ever UPDATE that row, never create one.

Idempotency: each event is recorded in stripe_events keyed by stripe_event_id
before processing; already-processed events are skipped.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.stripe_event import StripeEvent
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.stripe_service import StripeService

logger = logging.getLogger(__name__)

_STRIPE_STATUS_MAP = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "incomplete": "past_due",
    "incomplete_expired": "canceled",
    "canceled": "canceled",
}


class StripeWebhookHandler:
    """Routes verified Stripe events to per-type handlers."""

    def __init__(self, stripe_service: StripeService):
        self.stripe_service = stripe_service

    def process_event(self, event: dict, db: Session) -> bool:
        """Process a Stripe webhook event with idempotency. Returns False if already processed."""
        event_id = event["id"]
        event_type = event["type"]
        obj = event.get("data", {}).get("object", {})

        existing = db.scalar(select(StripeEvent).where(StripeEvent.stripe_event_id == event_id))
        if existing and existing.processed_at:
            logger.info("Event %s already processed, skipping", event_id)
            return False

        workspace_sub = self._resolve_workspace_sub(db, obj)

        if not existing:
            existing = StripeEvent(
                stripe_event_id=event_id,
                event_type=event_type,
                workspace_id=workspace_sub.workspace_id if workspace_sub else None,
                payload=obj,
            )
            db.add(existing)
            db.flush()

        handler = getattr(self, f"handle_{event_type.replace('.', '_')}", None)
        if not handler:
            logger.info("No handler for event type %s, marking as processed (no-op)", event_type)
            existing.processed_at = datetime.now(timezone.utc)
            db.commit()
            return True

        handler(obj, workspace_sub, db)
        existing.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Processed event %s (%s)", event_id, event_type)
        return True

    def _resolve_workspace_sub(self, db: Session, obj: dict) -> WorkspaceSubscription | None:
        """Resolve the WorkspaceSubscription row for a Stripe object via metadata, falling back
        to matching by Stripe customer id (covers invoice events, which carry no metadata)."""
        workspace_id = obj.get("metadata", {}).get("workspace_id")
        if workspace_id:
            try:
                return db.scalar(
                    select(WorkspaceSubscription).where(
                        WorkspaceSubscription.workspace_id == uuid.UUID(workspace_id)
                    )
                )
            except ValueError:
                pass

        customer_id = obj.get("customer")
        if customer_id:
            return db.scalar(
                select(WorkspaceSubscription).where(
                    WorkspaceSubscription.stripe_customer_id == customer_id
                )
            )
        return None

    def _sync_plan_from_subscription(self, db: Session, subscription: dict) -> Plan | None:
        items = subscription.get("items", {}).get("data", [])
        if not items:
            return None
        price_id = items[0].get("price", {}).get("id")
        if not price_id:
            return None
        plan_code = self.stripe_service.plan_code_for_price_id(price_id)
        if not plan_code:
            logger.warning("Unrecognized Stripe price_id %s — cannot sync plan", price_id)
            return None
        return db.scalar(select(Plan).where(Plan.code == plan_code))

    # ── Event handlers ───────────────────────────────────────────────────────

    def handle_customer_subscription_created(
        self, subscription: dict, workspace_sub: WorkspaceSubscription | None, db: Session
    ) -> None:
        if workspace_sub is None:
            logger.error("subscription.created with no resolvable workspace: %s", subscription.get("id"))
            return

        plan = self._sync_plan_from_subscription(db, subscription)
        if plan:
            workspace_sub.plan_id = plan.id

        workspace_sub.stripe_subscription_id = subscription["id"]
        workspace_sub.stripe_customer_id = subscription["customer"]
        workspace_sub.status = _STRIPE_STATUS_MAP.get(subscription.get("status"), "active")
        workspace_sub.auto_renew = True
        workspace_sub.cancel_at_period_end = False
        self._apply_period(workspace_sub, subscription)

        db.commit()
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_sub.workspace_id,
            action="subscription_created",
            status="success",
            stripe_response={"subscription_id": subscription["id"], "plan": plan.code if plan else None},
        )

    def handle_customer_subscription_updated(
        self, subscription: dict, workspace_sub: WorkspaceSubscription | None, db: Session
    ) -> None:
        if workspace_sub is None:
            logger.warning("subscription.updated with no resolvable workspace: %s", subscription.get("id"))
            return

        plan = self._sync_plan_from_subscription(db, subscription)
        if plan:
            workspace_sub.plan_id = plan.id

        workspace_sub.status = _STRIPE_STATUS_MAP.get(subscription.get("status"), workspace_sub.status)
        workspace_sub.cancel_at_period_end = bool(subscription.get("cancel_at_period_end"))
        workspace_sub.auto_renew = not workspace_sub.cancel_at_period_end
        self._apply_period(workspace_sub, subscription)

        db.commit()
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_sub.workspace_id,
            action="subscription_updated",
            status="success",
            stripe_response={"subscription_id": subscription["id"], "plan": plan.code if plan else None},
        )

    def handle_customer_subscription_deleted(
        self, subscription: dict, workspace_sub: WorkspaceSubscription | None, db: Session
    ) -> None:
        if workspace_sub is None:
            logger.warning("subscription.deleted with no resolvable workspace: %s", subscription.get("id"))
            return

        starter = db.scalar(select(Plan).where(Plan.code == "starter"))
        if starter:
            workspace_sub.plan_id = starter.id

        workspace_sub.status = "canceled"
        workspace_sub.auto_renew = False
        workspace_sub.cancel_at_period_end = False
        workspace_sub.stripe_subscription_id = None
        workspace_sub.cancelled_at = datetime.now(timezone.utc)
        workspace_sub.cancellation_reason = (
            subscription.get("cancellation_details", {}).get("reason") or "cancelled_by_stripe"
        )

        db.commit()
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_sub.workspace_id,
            action="subscription_deleted",
            status="success",
            stripe_response={"subscription_id": subscription.get("id")},
        )

    def handle_invoice_payment_succeeded(
        self, invoice: dict, workspace_sub: WorkspaceSubscription | None, db: Session
    ) -> None:
        if workspace_sub is None:
            return
        if workspace_sub.status == "past_due":
            workspace_sub.status = "active"
            db.commit()
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_sub.workspace_id,
            action="payment_succeeded",
            status="success",
            stripe_response={"invoice_id": invoice.get("id"), "amount_paid": invoice.get("amount_paid")},
        )

    def handle_invoice_payment_failed(
        self, invoice: dict, workspace_sub: WorkspaceSubscription | None, db: Session
    ) -> None:
        if workspace_sub is None:
            return
        workspace_sub.status = "past_due"
        db.commit()
        self.stripe_service.log_sync_action(
            db,
            workspace_id=workspace_sub.workspace_id,
            action="payment_failed",
            status="failed",
            error_message=f"Invoice {invoice.get('id')} payment failed",
        )

    @staticmethod
    def _apply_period(workspace_sub: WorkspaceSubscription, subscription: dict) -> None:
        start = subscription.get("current_period_start")
        end = subscription.get("current_period_end")
        if start:
            workspace_sub.current_period_start = datetime.fromtimestamp(start, tz=timezone.utc)
        if end:
            workspace_sub.current_period_end = datetime.fromtimestamp(end, tz=timezone.utc)
