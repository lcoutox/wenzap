"""
Playground Sessions service.

Manages agent_playground_sessions and agent_playground_messages.
All operations enforce workspace + agent isolation.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.agent_playground_message import AgentPlaygroundMessage
from app.models.agent_playground_session import AgentPlaygroundSession

_DEFAULT_TITLE = "Nova conversa"
_TITLE_MAX_LEN = 80


def create_session(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentPlaygroundSession:
    """Create and commit a new session. Used by the CRUD endpoint."""
    session = _build_session(db, workspace_id, agent_id, user_id)
    db.commit()
    db.refresh(session)
    return session


def create_session_pending(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentPlaygroundSession:
    """Add a new session to the current unit-of-work without committing.

    The caller is responsible for flushing (to get the PK) and committing.
    Used by agent_test_service so that session creation, message saves and
    credit increment all land in a single atomic transaction.
    """
    return _build_session(db, workspace_id, agent_id, user_id)


def _build_session(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AgentPlaygroundSession:
    # Generate UUID explicitly so session.id is available before flush,
    # allowing callers to use it as a FK in the same unit of work.
    session = AgentPlaygroundSession(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        agent_id=agent_id,
        user_id=user_id,
        title=_DEFAULT_TITLE,
    )
    db.add(session)
    return session


def list_sessions(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> list[AgentPlaygroundSession]:
    return list(
        db.scalars(
            select(AgentPlaygroundSession)
            .where(
                AgentPlaygroundSession.workspace_id == workspace_id,
                AgentPlaygroundSession.agent_id == agent_id,
            )
            .order_by(AgentPlaygroundSession.updated_at.desc())
        )
    )


def get_session_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    session_id: uuid.UUID,
) -> AgentPlaygroundSession:
    session = db.scalar(
        select(AgentPlaygroundSession).where(
            AgentPlaygroundSession.id == session_id,
            AgentPlaygroundSession.workspace_id == workspace_id,
            AgentPlaygroundSession.agent_id == agent_id,
        )
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sessão não encontrada.")
    return session


def get_session_with_messages(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    session_id: uuid.UUID,
) -> tuple[AgentPlaygroundSession, list[AgentPlaygroundMessage]]:
    session = get_session_or_404(db, workspace_id, agent_id, session_id)
    messages = list(
        db.scalars(
            select(AgentPlaygroundMessage)
            .where(AgentPlaygroundMessage.session_id == session_id)
            .order_by(AgentPlaygroundMessage.created_at.asc())
        )
    )
    return session, messages


def delete_session(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    session_id: uuid.UUID,
) -> None:
    session = get_session_or_404(db, workspace_id, agent_id, session_id)
    db.delete(session)
    db.commit()


def save_user_message(
    db: Session,
    session_id: uuid.UUID,
    content: str,
) -> AgentPlaygroundMessage:
    msg = AgentPlaygroundMessage(
        session_id=session_id,
        role="user",
        content=content,
        agent_test_run_id=None,
    )
    db.add(msg)
    return msg


def save_assistant_message(
    db: Session,
    session_id: uuid.UUID,
    content: str,
    agent_test_run_id: uuid.UUID | None,
) -> AgentPlaygroundMessage:
    msg = AgentPlaygroundMessage(
        session_id=session_id,
        role="assistant",
        content=content,
        agent_test_run_id=agent_test_run_id,
    )
    db.add(msg)
    return msg


def touch_session(db: Session, session: AgentPlaygroundSession) -> None:
    """Bump updated_at to now so the session surfaces at the top of the list."""
    db.execute(
        update(AgentPlaygroundSession)
        .where(AgentPlaygroundSession.id == session.id)
        .values(updated_at=func.now())
    )


def update_session_title_from_first_message(
    db: Session,
    session: AgentPlaygroundSession,
    content: str,
) -> None:
    """Set title to the first user message if session still has the default title."""
    if session.title != _DEFAULT_TITLE:
        return
    candidate = content.strip()[:_TITLE_MAX_LEN]
    if not candidate:
        return
    db.execute(
        update(AgentPlaygroundSession)
        .where(AgentPlaygroundSession.id == session.id)
        .values(title=candidate)
    )
