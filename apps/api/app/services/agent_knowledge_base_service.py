"""
Agent ↔ Knowledge Base connection service — Phase 4.1.4.

Rules:
- agent and KB must both belong to the current workspace (tenant isolation).
- Archived KBs cannot be connected and are excluded from listings.
- Connections are hard-deleted on disconnect (no soft-delete).
- If a connection exists but is_active=False, reconnecting reactivates it (200).
- If a connection exists and is_active=True, reconnecting returns 409.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_knowledge_base import AgentKnowledgeBase
from app.models.knowledge_base import KnowledgeBase
from app.schemas.agent_knowledge_base import AgentKnowledgeBaseOut, AgentKnowledgeBaseUpdate

# ── Public API ────────────────────────────────────────────────────────────────

def list_agent_knowledge_bases(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> list[AgentKnowledgeBaseOut]:
    _get_agent_or_404(db, workspace_id, agent_id)

    rows = db.execute(
        select(AgentKnowledgeBase, KnowledgeBase)
        .join(KnowledgeBase, KnowledgeBase.id == AgentKnowledgeBase.knowledge_base_id)
        .where(
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.status != "archived",
        )
        .order_by(AgentKnowledgeBase.created_at.desc())
    ).all()

    return [_to_out(conn, kb) for conn, kb in rows]


def connect_knowledge_base(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> tuple[AgentKnowledgeBaseOut, bool]:
    """Connect a KB to an agent.

    Returns (out, created) where created=True means 201, False means 200 (reactivated).
    """
    _get_agent_or_404(db, workspace_id, agent_id)
    kb = _get_kb_or_404(db, workspace_id, kb_id)

    existing = db.scalar(
        select(AgentKnowledgeBase).where(
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.knowledge_base_id == kb_id,
        )
    )

    if existing is not None:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Esta base de conhecimento já está conectada ao agente.",
            )
        # Reactivate existing inactive connection
        existing.is_active = True
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return _to_out(existing, kb), False

    conn = AgentKnowledgeBase(
        workspace_id=workspace_id,
        agent_id=agent_id,
        knowledge_base_id=kb_id,
        is_active=True,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return _to_out(conn, kb), True


def update_agent_knowledge_base(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
    data: AgentKnowledgeBaseUpdate,
) -> AgentKnowledgeBaseOut:
    _get_agent_or_404(db, workspace_id, agent_id)

    conn, kb = _get_connection_with_kb_or_404(db, workspace_id, agent_id, kb_id)

    conn.is_active = data.is_active
    conn.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(conn)
    return _to_out(conn, kb)


def disconnect_knowledge_base(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> None:
    _get_agent_or_404(db, workspace_id, agent_id)

    conn = db.scalar(
        select(AgentKnowledgeBase).where(
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.knowledge_base_id == kb_id,
            AgentKnowledgeBase.workspace_id == workspace_id,
        )
    )
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conexão não encontrada.",
        )
    db.delete(conn)
    db.commit()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_agent_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agente não encontrado.",
        )
    return agent


def _get_kb_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> KnowledgeBase:
    """Return KB if it exists in this workspace and is not archived."""
    kb = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.status != "archived",
        )
    )
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Base de conhecimento não encontrada.",
        )
    return kb


def _get_connection_with_kb_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> tuple[AgentKnowledgeBase, KnowledgeBase]:
    row = db.execute(
        select(AgentKnowledgeBase, KnowledgeBase)
        .join(KnowledgeBase, KnowledgeBase.id == AgentKnowledgeBase.knowledge_base_id)
        .where(
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.knowledge_base_id == kb_id,
            AgentKnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.status != "archived",
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conexão não encontrada.",
        )
    return row[0], row[1]


def _to_out(conn: AgentKnowledgeBase, kb: KnowledgeBase) -> AgentKnowledgeBaseOut:
    return AgentKnowledgeBaseOut(
        id=conn.id,
        workspace_id=conn.workspace_id,
        agent_id=conn.agent_id,
        knowledge_base_id=conn.knowledge_base_id,
        is_active=conn.is_active,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
        knowledge_base_name=kb.name,
        knowledge_base_status=kb.status,
    )
