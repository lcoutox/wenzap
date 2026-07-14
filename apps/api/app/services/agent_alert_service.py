"""Agent Alert Service — notifies workspace admins when agent fails."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def notify_agent_error(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    conversation_id: uuid.UUID,
    error_code: str,
    error_message: str,
    error_details: dict | None = None,
) -> None:
    """
    Notify workspace admin when agent fails.

    Creates an alert dashboard entry visible to the admin.
    For now, we log the alert and can later integrate with:
    - Dashboard notifications
    - Email notifications
    - Slack webhooks
    """
    try:
        from app.models.agent_alert import AgentAlert

        alert = AgentAlert(
            workspace_id=workspace_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            error_code=error_code,
            error_message_user="Seu agente está temporariamente indisponível. Houve uma instabilidade ao processar mensagens.",
            error_message_admin=error_message,
            error_details_json=error_details or {},
            is_read=False,
        )
        db.add(alert)
        db.flush()  # Ensure alert is created before commit

        logger.info(
            "agent_alert_created workspace_id=%s agent_id=%s conversation_id=%s error_code=%s",
            workspace_id, agent_id, conversation_id, error_code,
        )

        # TODO: Emit event for dashboard subscription
        # TODO: Send email notification to workspace admins
        # TODO: Send Slack notification if configured

    except Exception as exc:
        # Don't let alert creation fail the agent reply
        logger.exception(
            "agent_alert_creation_failed workspace_id=%s agent_id=%s error=%s",
            workspace_id, agent_id, str(exc),
        )
