"""
Follow-up sweep scheduler — follow-up-tool-prd.md.

Same shape as pipeline_stay_limit_scheduler.py (periodic in-process sweep,
single daemon thread started at app startup) but the concurrency guard is a
unique DB constraint instead of a compare-and-swap UPDATE: each sweep pass
"claims" a (conversation, step, silence_anchor) by inserting a
ConversationFollowUp row first — if that insert collides with the unique
constraint (another process already claimed it), we back off. Only after a
successful claim do we spend an LLM call generating the actual message.

MVP-appropriate for the current single-replica deployment, same caveat as
the Pipeline.2 scheduler: dies on redeploy mid-wait, silently resumes on the
next boot's sweep pass (fine at hour granularity). The claim-based unique
constraint is what makes this safe to later run across multiple replicas
without a redesign.
"""

import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine
from app.models.agent import Agent
from app.models.agent_follow_up_settings import AgentFollowUpSettings
from app.models.agent_follow_up_step import AgentFollowUpStep
from app.models.conversation import Conversation
from app.models.conversation_follow_up import ConversationFollowUp
from app.services.conversation_follow_up_service import generate_and_send_follow_up
from app.services.plan_feature_service import workspace_allows_feature

logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_SECONDS = 300  # 5 min — hour-granularity delays don't need 60s precision
_ELIGIBLE_CHANNELS = ("whatsapp", "web_widget")
_ELIGIBLE_STATUSES = ("open", "pending")


def start_background_sweep() -> None:
    t = threading.Thread(target=_sweep_loop, daemon=True, name="conversation-follow-up-sweep")
    t.start()
    logger.info("conversation_follow_up_sweep started interval=%ds", _SWEEP_INTERVAL_SECONDS)


def _sweep_loop() -> None:
    while True:
        time.sleep(_SWEEP_INTERVAL_SECONDS)
        db = Session(engine)
        try:
            sent = run_sweep_once(db)
            if sent:
                logger.info("conversation_follow_up_sweep sent=%d", sent)
        except Exception:
            logger.exception("conversation_follow_up_sweep unexpected error")
        finally:
            db.close()


def run_sweep_once(db: Session) -> int:
    """One sweep pass. Extracted so tests can call it directly."""
    now = datetime.now(timezone.utc)

    candidates = db.execute(
        select(
            Conversation.id,
            Conversation.workspace_id,
            Conversation.agent_id,
            Conversation.last_customer_message_at,
        ).where(
            Conversation.ai_enabled.is_(True),
            Conversation.assigned_user_id.is_(None),
            Conversation.status.in_(_ELIGIBLE_STATUSES),
            Conversation.channel_type.in_(_ELIGIBLE_CHANNELS),
            Conversation.last_customer_message_at.is_not(None),
            Conversation.agent_id.is_not(None),
        )
    ).all()

    sent_count = 0
    for row in candidates:
        if _maybe_send_follow_up(
            db, now, row.id, row.workspace_id, row.agent_id, row.last_customer_message_at
        ):
            sent_count += 1
    return sent_count


def _maybe_send_follow_up(
    db: Session,
    now: datetime,
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    last_customer_message_at: datetime,
) -> bool:
    if not workspace_allows_feature(db, workspace_id, "follow_up"):
        return False

    settings = db.scalar(
        select(AgentFollowUpSettings).where(AgentFollowUpSettings.agent_id == agent_id)
    )
    if settings is None or not settings.is_enabled:
        return False

    steps = list(
        db.scalars(
            select(AgentFollowUpStep)
            .where(AgentFollowUpStep.agent_id == agent_id)
            .order_by(AgentFollowUpStep.step_order)
        )
    )
    if not steps:
        return False

    sent_this_period = db.scalar(
        select(ConversationFollowUp).where(
            ConversationFollowUp.conversation_id == conversation_id,
            ConversationFollowUp.silence_anchor == last_customer_message_at,
        ).order_by(ConversationFollowUp.step_order.desc()).limit(1)
    )
    next_index = (sent_this_period.step_order + 1) if sent_this_period else 0
    if next_index >= len(steps):
        return False  # all configured steps already sent for this silence period

    next_step = steps[next_index]
    elapsed_hours = (now - last_customer_message_at).total_seconds() / 3600
    if elapsed_hours < next_step.delay_hours:
        return False

    # Claim first — the unique constraint on (conversation_id, step_order,
    # silence_anchor) is the real concurrency guard (see model docstring).
    claim = ConversationFollowUp(
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        agent_id=agent_id,
        step_order=next_step.step_order,
        silence_anchor=last_customer_message_at,
        conversation_message_id=None,
        sent_at=now,
    )
    db.add(claim)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False

    conversation = db.get(Conversation, conversation_id)
    agent = db.get(Agent, agent_id)
    if conversation is None or agent is None or agent.status != "active":
        db.rollback()
        return False

    sent = generate_and_send_follow_up(
        db,
        workspace_id=workspace_id,
        conversation=conversation,
        agent=agent,
        step_number=next_index + 1,
        total_steps=len(steps),
        hours_silent=elapsed_hours,
        custom_instructions=settings.custom_instructions,
        claim=claim,
    )
    if not sent:
        # Release the claim so this step can be retried on a later sweep
        # (e.g. credits were insufficient this pass but reset next period).
        db.rollback()
        return False
    return True
