import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace import WorkspaceUpdate


def update_workspace(
    db: Session,
    workspace: Workspace,
    data: WorkspaceUpdate,
    current_user_role: MemberRole,
) -> Workspace:
    if current_user_role not in (MemberRole.owner, MemberRole.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permissões insuficientes."
        )

    if data.name is not None:
        workspace.name = data.name
        # A deliberate rename permanently opts this workspace out of the
        # onboarding company_name auto-sync (onboarding_service.py) — it
        # must never overwrite a name someone chose on purpose.
        workspace.name_is_default = False
    if data.slug is not None:
        existing = db.scalar(
            select(Workspace).where(Workspace.slug == data.slug, Workspace.id != workspace.id)
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug já está em uso.")
        workspace.slug = data.slug

    db.commit()
    db.refresh(workspace)
    return workspace


def get_current_member_role(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> MemberRole:
    """Returns the role of an *active* member. Raises 403 if not found or inactive."""
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == MemberStatus.active,
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não é um membro ativo.")
    return MemberRole(member.role)
