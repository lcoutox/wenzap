import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.contact import (
    ContactCreate,
    ContactListOut,
    ContactOut,
    ContactUpdate,
    ContactVariableCreate,
    ContactVariableOut,
    ContactVariableUpdate,
)
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
            detail="Permissões insuficientes.",
        )
    return role


# ── Contact CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=ContactListOut)
def list_contacts(
    q: str | None = Query(default=None, description="Busca por nome, e-mail ou telefone"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ContactListOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return contact_service.list_contacts(
        db, current_workspace.id, q=q, limit=limit, offset=offset
    )


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


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    contact_service.delete_contact(db, current_workspace.id, contact_id)


# ── Contact Variables ─────────────────────────────────────────────────────────

@router.get("/{contact_id}/variables", response_model=list[ContactVariableOut])
def list_variables(
    contact_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[ContactVariableOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return contact_service.list_variables(db, current_workspace.id, contact_id)


@router.post(
    "/{contact_id}/variables",
    response_model=ContactVariableOut,
    status_code=status.HTTP_201_CREATED,
)
def create_variable(
    contact_id: uuid.UUID,
    data: ContactVariableCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ContactVariableOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return contact_service.create_variable(db, current_workspace.id, contact_id, data)


@router.patch(
    "/{contact_id}/variables/{variable_id}",
    response_model=ContactVariableOut,
)
def update_variable(
    contact_id: uuid.UUID,
    variable_id: uuid.UUID,
    data: ContactVariableUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ContactVariableOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return contact_service.update_variable(
        db, current_workspace.id, contact_id, variable_id, data
    )


@router.delete(
    "/{contact_id}/variables/{variable_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_variable(
    contact_id: uuid.UUID,
    variable_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    contact_service.delete_variable(db, current_workspace.id, contact_id, variable_id)
