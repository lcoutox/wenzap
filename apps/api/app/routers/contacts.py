import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate
from app.services import contact_service
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/contacts", dependencies=[Depends(get_verified_user)])

_READ_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member, MemberRole.viewer}
_WRITE_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member}


def _require_role(
    allowed: set[MemberRole],
    db: Session,
    workspace: Workspace,
    user: User,
) -> MemberRole:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return role


@router.get("", response_model=list[ContactOut])
def list_contacts(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[ContactOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return contact_service.list_contacts(db, current_workspace.id, skip=skip, limit=limit)


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    data: ContactCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ContactOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return contact_service.create_contact(db, current_workspace.id, data)


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ContactOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return contact_service.get_contact_or_404(db, current_workspace.id, contact_id)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: uuid.UUID,
    data: ContactUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ContactOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return contact_service.update_contact(db, current_workspace.id, contact_id, data)
