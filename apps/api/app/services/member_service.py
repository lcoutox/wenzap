import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.member import MemberOut


def list_members(db: Session, workspace_id: uuid.UUID) -> list[MemberOut]:
    """Returns all members of a workspace with user data joined in a single query."""
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at)
    ).all()

    return [
        MemberOut(
            id=member.id,
            user_id=member.user_id,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            role=MemberRole(member.role),
            status=MemberStatus(member.status),
            created_at=member.created_at,
        )
        for member, user in rows
    ]


def get_member_out(db: Session, workspace_id: uuid.UUID, member_id: uuid.UUID) -> MemberOut:
    """Returns a single member with user data. Raises 404 if not found in this workspace."""
    row = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    ).first()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    member, user = row
    return MemberOut(
        id=member.id,
        user_id=member.user_id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        role=MemberRole(member.role),
        status=MemberStatus(member.status),
        created_at=member.created_at,
    )


def update_member_role(
    db: Session,
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    new_role: MemberRole,
    requester_role: MemberRole,
) -> uuid.UUID:
    """
    Updates the role of a workspace member.
    Returns the member_id so the caller can fetch fresh data.
    Raises 403 if requester is not an owner, 404 if member not found in this workspace.
    """
    if requester_role != MemberRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can change roles"
        )

    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.id == member_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if MemberRole(member.role) == MemberRole.owner and new_role != MemberRole.owner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove owner role without transferring ownership",
        )

    member.role = new_role.value
    db.commit()
    return member.id
