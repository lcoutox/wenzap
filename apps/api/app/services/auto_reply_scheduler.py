"""
Auto Reply Scheduler — AI Reply UX.1.

Implements debounced automatic agent replies using a background daemon thread.

Design:
- The caller schedules a reply by providing the trigger message ID.
- A daemon thread sleeps for `delay_seconds` then checks whether the trigger
  message is still the latest inbound customer message in the conversation.
- If a newer customer message arrived during the sleep, the thread exits silently
  (no-op); another thread will have been scheduled for that newer message.
- Credits are consumed ONLY when the LLM actually generates a reply, never in
  no-op threads.

Why threads instead of asyncio.create_task:
- FastAPI sync route handlers execute in a thread-pool executor, not on the
  event loop — so asyncio.create_task is not available from those call sites.
- time.sleep inside a daemon thread does NOT block the HTTP response; the
  request completes as soon as the thread is started.
- No Celery is configured in this project (MVP stage).
"""

import logging
import threading
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage

logger = logging.getLogger(__name__)


def schedule_agent_auto_reply(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    agent_id: uuid.UUID,
    trigger_message_id: uuid.UUID,
    delay_seconds: int,
    db: Session | None = None,
) -> None:
    """
    Schedule an auto-reply to fire after *delay_seconds*.

    When delay_seconds == 0 the reply runs synchronously in the caller's DB
    session (preserving existing behaviour and test compatibility).

    When delay_seconds > 0 a daemon thread is started so the HTTP response
    is not held open during the sleep.  The thread opens its own DB session.

    If a newer inbound customer message arrives before the thread wakes up,
    the scheduled reply is silently skipped (no-op, no credits consumed).
    """
    if delay_seconds <= 0:
        # Synchronous path — keep existing behaviour for "Imediato".
        if db is not None:
            _execute_if_latest(db, workspace_id, conversation_id, agent_id, trigger_message_id)
        return

    t = threading.Thread(
        target=_run_auto_reply,
        args=(workspace_id, conversation_id, agent_id, trigger_message_id, delay_seconds),
        daemon=True,
        name=f"auto-reply-{conversation_id}-{trigger_message_id}",
    )
    t.start()


def _run_auto_reply(
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    agent_id: uuid.UUID,
    trigger_message_id: uuid.UUID,
    delay_seconds: int,
) -> None:
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    db: Session = Session(engine)
    try:
        _execute_if_latest(db, workspace_id, conversation_id, agent_id, trigger_message_id)
    except Exception:
        logger.exception(
            "auto_reply_scheduler unexpected error conversation=%s message=%s",
            conversation_id,
            trigger_message_id,
        )
    finally:
        db.close()


def _execute_if_latest(
    db: Session,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    agent_id: uuid.UUID,
    trigger_message_id: uuid.UUID,
) -> None:
    """
    Execute the agent reply only when trigger_message_id is still the most
    recent inbound customer message in the conversation.
    """
    # Load fresh conversation state — the object may have changed since scheduling.
    conversation = db.scalar(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    if conversation is None:
        logger.info(
            "auto_reply_scheduler skip conversation=%s not_found",
            conversation_id,
        )
        return

    # Verify that the latest inbound customer message is still our trigger.
    latest_customer_msg = db.scalar(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.direction == "inbound",
            ConversationMessage.sender_type == "customer",
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(1)
    )

    if latest_customer_msg is None or latest_customer_msg.id != trigger_message_id:
        logger.info(
            "auto_reply_scheduler skip conversation=%s message=%s reason=superseded "
            "latest_message=%s",
            conversation_id,
            trigger_message_id,
            latest_customer_msg.id if latest_customer_msg else None,
        )
        return

    logger.info(
        "auto_reply_scheduler firing conversation=%s message=%s",
        conversation_id,
        trigger_message_id,
    )

    from app.services.conversation_agent_reply_service import (  # noqa: PLC0415
        generate_conversation_agent_reply,
    )
    generate_conversation_agent_reply(
        db,
        workspace_id,
        conversation,
        latest_customer_msg,
    )
