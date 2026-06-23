import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseOut, KnowledgeBaseUpdate
from app.schemas.knowledge_chunk import KnowledgeChunkOut
from app.schemas.knowledge_source import KnowledgeSourceCreate, KnowledgeSourceOut
from app.services import knowledge_base_service, knowledge_source_service
from app.services.upload_source_service import upload_knowledge_source
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/knowledge-bases")

_READ_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member, MemberRole.viewer}
_WRITE_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member}
_ARCHIVE_ROLES = {MemberRole.owner, MemberRole.admin}


def _require_role(
    allowed: set[MemberRole],
    db: Session,
    workspace: Workspace,
    user: User,
) -> MemberRole:
    from fastapi import HTTPException

    role = get_current_member_role(db, workspace.id, user.id)
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return role


@router.get("", response_model=list[KnowledgeBaseOut])
def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[KnowledgeBaseOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return knowledge_base_service.list_knowledge_bases(db, current_workspace.id)


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeBaseOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return knowledge_base_service.create_knowledge_base(
        db, current_workspace.id, current_user.id, data
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
def get_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeBaseOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return knowledge_base_service.get_knowledge_base_or_404(db, current_workspace.id, kb_id)


@router.patch("/{kb_id}", response_model=KnowledgeBaseOut)
def update_knowledge_base(
    kb_id: uuid.UUID,
    data: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeBaseOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return knowledge_base_service.update_knowledge_base(db, current_workspace.id, kb_id, data)


@router.delete("/{kb_id}", response_model=KnowledgeBaseOut)
def archive_knowledge_base(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeBaseOut:
    _require_role(_ARCHIVE_ROLES, db, current_workspace, current_user)
    return knowledge_base_service.archive_knowledge_base(db, current_workspace.id, kb_id)


# ── Knowledge Sources ─────────────────────────────────────────────────────────

@router.get("/{kb_id}/sources", response_model=list[KnowledgeSourceOut])
def list_sources(
    kb_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[KnowledgeSourceOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return knowledge_source_service.list_sources(db, current_workspace.id, kb_id)


@router.post(
    "/{kb_id}/sources",
    response_model=KnowledgeSourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    kb_id: uuid.UUID,
    data: KnowledgeSourceCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeSourceOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return knowledge_source_service.create_source(
        db, current_workspace.id, kb_id, current_user.id, data
    )


@router.post(
    "/{kb_id}/sources/upload",
    response_model=KnowledgeSourceOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source(
    kb_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    source_category: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeSourceOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    file_data = await file.read()
    return upload_knowledge_source(
        db=db,
        workspace_id=current_workspace.id,
        kb_id=kb_id,
        user_id=current_user.id,
        file_data=file_data,
        filename=file.filename or "upload",
        content_type=file.content_type,
        title=title,
        source_category=source_category,
    )


@router.get("/{kb_id}/sources/{source_id}", response_model=KnowledgeSourceOut)
def get_source(
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeSourceOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return knowledge_source_service.get_source_or_404(
        db, current_workspace.id, kb_id, source_id
    )


@router.delete("/{kb_id}/sources/{source_id}", response_model=KnowledgeSourceOut)
def archive_source(
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeSourceOut:
    _require_role(_ARCHIVE_ROLES, db, current_workspace, current_user)
    return knowledge_source_service.archive_source(
        db, current_workspace.id, kb_id, source_id
    )


@router.post("/{kb_id}/sources/{source_id}/reprocess", response_model=KnowledgeSourceOut)
def reprocess_source(
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> KnowledgeSourceOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return knowledge_source_service.reprocess_source(
        db, current_workspace.id, kb_id, source_id
    )


@router.get(
    "/{kb_id}/sources/{source_id}/chunks",
    response_model=list[KnowledgeChunkOut],
)
def list_source_chunks(
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[KnowledgeChunkOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return knowledge_source_service.list_source_chunks(
        db, current_workspace.id, kb_id, source_id
    )
