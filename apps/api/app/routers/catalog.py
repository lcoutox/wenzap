import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.enums import MemberRole
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.catalog import (
    CatalogCategoryCreate,
    CatalogCategoryOut,
    CatalogCategoryUpdate,
    CatalogImportPreview,
    CatalogImportReport,
    CatalogItemCreate,
    CatalogItemFilters,
    CatalogItemOut,
    CatalogItemUpdate,
    CatalogMediaOut,
    CatalogMediaReorderItem,
    CatalogMediaUpdate,
)
from app.services import catalog_import_service, catalog_media_service, catalog_service
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/catalog", tags=["catalog"])

_READ_ROLES  = {MemberRole.owner, MemberRole.admin, MemberRole.member, MemberRole.viewer}
_WRITE_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member}
_ADMIN_ROLES = {MemberRole.owner, MemberRole.admin}


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


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CatalogCategoryOut])
def list_categories(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[CatalogCategoryOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return catalog_service.list_categories(
        db, current_workspace.id, include_inactive=include_inactive
    )


@router.post("/categories", response_model=CatalogCategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CatalogCategoryCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogCategoryOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return catalog_service.create_category(db, current_workspace.id, data)


@router.get("/categories/{category_id}", response_model=CatalogCategoryOut)
def get_category(
    category_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogCategoryOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return catalog_service.get_category_or_404(db, current_workspace.id, category_id)


@router.patch("/categories/{category_id}", response_model=CatalogCategoryOut)
def update_category(
    category_id: uuid.UUID,
    data: CatalogCategoryUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogCategoryOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return catalog_service.update_category(db, current_workspace.id, category_id, data)


@router.delete("/categories/{category_id}", response_model=CatalogCategoryOut)
def delete_category(
    category_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogCategoryOut:
    _require_role(_ADMIN_ROLES, db, current_workspace, current_user)
    return catalog_service.delete_category(db, current_workspace.id, category_id)


# ── Items ─────────────────────────────────────────────────────────────────────

@router.get("/items", response_model=list[CatalogItemOut])
def list_items(
    q: str | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    is_featured: bool | None = Query(default=None),
    has_price: bool | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_primary_media: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[CatalogItemOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    filters = CatalogItemFilters(
        q=q,
        category_id=category_id,
        status=status,
        is_featured=is_featured,
        has_price=has_price,
        tag=tag,
        limit=limit,
        offset=offset,
        include_primary_media=include_primary_media,
    )
    storage = None
    if include_primary_media:
        try:
            storage = catalog_media_service.get_storage_or_503()
        except Exception:
            storage = None
    return catalog_service.list_items(db, current_workspace.id, filters, storage=storage)


@router.post("/items", response_model=CatalogItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    data: CatalogItemCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogItemOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return catalog_service.create_item(db, current_workspace.id, data)


@router.get("/items/{item_id}", response_model=CatalogItemOut)
def get_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogItemOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return catalog_service.get_item_or_404(db, current_workspace.id, item_id)


@router.patch("/items/{item_id}", response_model=CatalogItemOut)
def update_item(
    item_id: uuid.UUID,
    data: CatalogItemUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogItemOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return catalog_service.update_item(db, current_workspace.id, item_id, data)


@router.delete("/items/{item_id}", response_model=CatalogItemOut)
def archive_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogItemOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return catalog_service.archive_item(db, current_workspace.id, item_id)


# ── Media endpoints ───────────────────────────────────────────────────────────

@router.get("/items/{item_id}/media", response_model=list[CatalogMediaOut])
def list_media(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[CatalogMediaOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    storage = catalog_media_service.get_storage_or_503()
    return catalog_media_service.list_media(db, current_workspace.id, item_id, storage)


@router.post(
    "/items/{item_id}/media",
    response_model=CatalogMediaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    display_name: str | None = Form(default=None),
    alt_text: str | None = Form(default=None),
    is_primary: bool = Form(default=False),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogMediaOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    storage = catalog_media_service.get_storage_or_503()
    file_data = await file.read()
    return catalog_media_service.upload_media(
        db=db,
        workspace_id=current_workspace.id,
        item_id=item_id,
        file_data=file_data,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        storage=storage,
        display_name=display_name,
        alt_text=alt_text,
        is_primary=is_primary,
    )


@router.get("/items/{item_id}/media/{media_id}", response_model=CatalogMediaOut)
def get_media(
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogMediaOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    storage = catalog_media_service.get_storage_or_503()
    return catalog_media_service.get_media_or_404(
        db, current_workspace.id, item_id, media_id, storage
    )


@router.patch("/items/{item_id}/media/{media_id}", response_model=CatalogMediaOut)
def update_media(
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    data: CatalogMediaUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogMediaOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    storage = catalog_media_service.get_storage_or_503()
    return catalog_media_service.update_media(
        db, current_workspace.id, item_id, media_id, data, storage
    )


@router.delete("/items/{item_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> None:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    storage = catalog_media_service.get_storage_or_503()
    catalog_media_service.delete_media(
        db, current_workspace.id, item_id, media_id, storage
    )


@router.post("/items/{item_id}/media/{media_id}/set-primary", response_model=CatalogMediaOut)
def set_primary(
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogMediaOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    storage = catalog_media_service.get_storage_or_503()
    return catalog_media_service.set_primary(
        db, current_workspace.id, item_id, media_id, storage
    )


@router.post("/items/{item_id}/media/reorder", response_model=list[CatalogMediaOut])
def reorder_media(
    item_id: uuid.UUID,
    items: list[CatalogMediaReorderItem],
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[CatalogMediaOut]:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    storage = catalog_media_service.get_storage_or_503()
    return catalog_media_service.reorder_media(
        db, current_workspace.id, item_id, items, storage
    )


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/import/preview", response_model=CatalogImportPreview)
async def import_preview(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogImportPreview:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    result = await catalog_import_service.preview(file)
    return CatalogImportPreview(
        filename=result.filename,
        total_rows=result.total_rows,
        columns=result.columns,
        rows_preview=[
            {"row_number": r.row_number, "values": r.values}
            for r in result.rows_preview
        ],
        warnings=result.warnings,
    )


@router.post("/import/commit", response_model=CatalogImportReport)
async def import_commit(
    file: UploadFile = File(...),
    mapping_json: str = Form(...),
    mode: str = Form(default="create_only"),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> CatalogImportReport:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)

    try:
        mapping = json.loads(mapping_json)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="mapping_json inválido.",
        )

    if mode not in {"create_only", "upsert_by_sku", "upsert_by_external_id"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Modo inválido: '{mode}'.",
        )

    result = await catalog_import_service.commit(
        db, current_workspace.id, file, mapping, mode  # type: ignore[arg-type]
    )
    return CatalogImportReport(
        total_rows=result.total_rows,
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=[
            {"row_number": e.row_number, "field": e.field, "message": e.message}
            for e in result.errors
        ],
        warnings=[
            {"row_number": w.row_number, "message": w.message}
            for w in result.warnings
        ],
    )
