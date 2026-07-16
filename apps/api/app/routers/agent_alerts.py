"""Agent Alerts routes — list and manage agent failure notifications."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_workspace, get_verified_user
from app.database import get_db
from app.models.agent_alert import AgentAlert
from app.models.workspace import Workspace

router = APIRouter(
    prefix="/agent-alerts",
    tags=["Agent Alerts"],
    dependencies=[Depends(get_verified_user)],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AgentAlertOut:
    """Agent alert response."""
    def __init__(self, alert: AgentAlert):
        self.id = str(alert.id)
        self.workspace_id = str(alert.workspace_id)
        self.agent_id = str(alert.agent_id)
        self.conversation_id = str(alert.conversation_id)
        self.error_code = alert.error_code
        self.error_message_user = alert.error_message_user
        self.error_message_admin = alert.error_message_admin
        self.is_read = alert.is_read
        self.created_at = alert.created_at.isoformat()
        self.read_at = alert.read_at.isoformat() if alert.read_at else None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[dict])
async def list_agent_alerts(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    is_read: bool | None = Query(None, description="Filter by read status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    List agent alerts for the workspace.

    Unread alerts are returned first, sorted by creation date (newest first).
    """
    query = select(AgentAlert).where(
        AgentAlert.workspace_id == workspace.id
    )

    if is_read is not None:
        query = query.where(AgentAlert.is_read == is_read)

    # Sort: unread first, then by created_at desc
    query = query.order_by(
        AgentAlert.is_read.asc(),
        desc(AgentAlert.created_at),
    ).limit(limit).offset(offset)

    alerts = db.scalars(query).all()
    return [
        {
            "id": str(alert.id),
            "agent_id": str(alert.agent_id),
            "conversation_id": str(alert.conversation_id),
            "error_code": alert.error_code,
            "error_message_user": alert.error_message_user,
            "error_message_admin": alert.error_message_admin,
            "is_read": alert.is_read,
            "created_at": alert.created_at.isoformat(),
        }
        for alert in alerts
    ]


@router.get("/unread-count")
async def get_unread_count(
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    """Get count of unread agent alerts."""
    count = db.scalar(
        select(func.count(AgentAlert.id)).where(
            and_(
                AgentAlert.workspace_id == workspace.id,
                AgentAlert.is_read == False,  # noqa: E712
            )
        )
    )
    return {"unread_count": count or 0}


@router.patch("/{alert_id}/read")
async def mark_alert_as_read(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    """Mark an alert as read."""
    from datetime import datetime, timezone

    alert = db.scalar(
        select(AgentAlert).where(
            and_(
                AgentAlert.id == alert_id,
                AgentAlert.workspace_id == workspace.id,
            )
        )
    )

    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")

    alert.is_read = True
    alert.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)

    return {
        "id": str(alert.id),
        "is_read": alert.is_read,
        "read_at": alert.read_at.isoformat(),
    }


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
):
    """Delete an alert."""
    alert = db.scalar(
        select(AgentAlert).where(
            and_(
                AgentAlert.id == alert_id,
                AgentAlert.workspace_id == workspace.id,
            )
        )
    )

    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")

    db.delete(alert)
    db.commit()

    return {"deleted": True}