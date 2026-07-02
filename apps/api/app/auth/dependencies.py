"""
Authentication and workspace resolution dependencies.

get_current_user reads the wenzap_session cookie and resolves the session
from auth_sessions. get_current_workspace resolves workspace context from
the authenticated user.
"""

import uuid

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import get_session_by_token
from app.config import settings
from app.database import get_db
from app.enums import MemberStatus, WorkspaceStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    session = get_session_by_token(db, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked"
        )

    # Commit here so last_seen_at is persisted even on read-only routes
    # that never call db.commit() themselves.
    db.commit()

    user = db.scalar(select(User).where(User.id == session.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def get_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Requires authentication AND email_verified=True."""
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-mail não verificado. Confirme seu e-mail para continuar.",
        )
    return current_user


def get_current_workspace(
    x_workspace_id: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    """
    Resolves the current workspace from the authenticated user context.

    Resolution order:
    1. X-Workspace-Id header — validated against *active* user membership.
       The header selects a workspace but does not grant access by itself.
    2. First active workspace of the user (ordered by created_at).
    3. No active workspace → 404.

    Inactive memberships are never used for workspace resolution.
    """
    if x_workspace_id:
        try:
            ws_id = uuid.UUID(x_workspace_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid workspace id"
            )

        member = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == ws_id,
                WorkspaceMember.user_id == current_user.id,
                WorkspaceMember.status == MemberStatus.active,
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not an active member of this workspace",
            )

        workspace = db.scalar(
            select(Workspace).where(
                Workspace.id == ws_id,
                Workspace.status == WorkspaceStatus.active,
            )
        )
        if workspace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found"
            )
        return workspace

    # No header — use the first active workspace the user actively belongs to.
    member = db.scalar(
        select(WorkspaceMember)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(
            WorkspaceMember.user_id == current_user.id,
            WorkspaceMember.status == MemberStatus.active,
            Workspace.status == WorkspaceStatus.active,
        )
        .order_by(Workspace.created_at)
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active workspace found for user",
        )

    workspace = db.scalar(select(Workspace).where(Workspace.id == member.workspace_id))
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace
