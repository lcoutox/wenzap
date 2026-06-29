"""
Catalog Media service — upload, list, update, delete, reorder, set-primary.

All mutations are workspace-isolated. Storage is abstracted behind StorageProvider.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.catalog_item import CatalogItem
from app.models.catalog_media import CatalogMedia
from app.schemas.catalog import CatalogMediaOut, CatalogMediaReorderItem, CatalogMediaUpdate
from app.services.storage.base import StorageError, StorageProvider

# ── MIME type registry ────────────────────────────────────────────────────────

_IMAGE_MIMES = frozenset({
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
})

_DOCUMENT_MIMES = frozenset({
    "application/pdf",
})

_ALLOWED_MIMES: frozenset[str] = _IMAGE_MIMES | _DOCUMENT_MIMES

_PRESIGNED_URL_EXPIRY = 3600  # 1 hour


def _derive_file_type(mime_type: str) -> str:
    if mime_type in _IMAGE_MIMES:
        return "image"
    if mime_type in _DOCUMENT_MIMES:
        return "document"
    return "other"


def _size_limit_for(mime_type: str) -> int:
    if mime_type in _IMAGE_MIMES:
        return settings.catalog_media_max_image_bytes
    if mime_type in _DOCUMENT_MIMES:
        return settings.catalog_media_max_document_bytes
    return settings.max_file_size_bytes


def _sanitize_filename(filename: str) -> str:
    """Return a safe, lowercase filename suitable for use in a storage key."""
    name = filename.strip()
    # Keep only alphanumeric, dash, underscore, dot.
    name = re.sub(r"[^\w.\-]", "_", name, flags=re.ASCII)
    # Collapse multiple underscores/dots.
    name = re.sub(r"[_]{2,}", "_", name)
    # Remove leading dots to prevent hidden-file names.
    name = name.lstrip(".")
    return name.lower() or "file"


def _build_key(
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    filename: str,
) -> str:
    safe = _sanitize_filename(filename)
    return f"workspaces/{workspace_id}/catalog/items/{item_id}/{media_id}-{safe}"


def _get_item_or_404(db: Session, workspace_id: uuid.UUID, item_id: uuid.UUID) -> CatalogItem:
    item = db.scalar(
        select(CatalogItem).where(
            CatalogItem.id == item_id,
            CatalogItem.workspace_id == workspace_id,
            CatalogItem.status != "archived",
        )
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")
    return item


def _get_media_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    media_id: uuid.UUID,
) -> CatalogMedia:
    media = db.scalar(
        select(CatalogMedia).where(
            CatalogMedia.id == media_id,
            CatalogMedia.item_id == item_id,
            CatalogMedia.workspace_id == workspace_id,
        )
    )
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found.")
    return media


def _attach_urls(media: CatalogMedia, storage: StorageProvider) -> CatalogMediaOut:
    """Build a CatalogMediaOut with presigned preview/download URLs."""
    try:
        preview_url = storage.generate_presigned_url(media.file_key, _PRESIGNED_URL_EXPIRY)
        download_url = preview_url
    except StorageError:
        preview_url = None
        download_url = None

    out = CatalogMediaOut.model_validate(media)
    out.preview_url = preview_url
    out.download_url = download_url
    return out


# ── Public API ────────────────────────────────────────────────────────────────

def list_media(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    storage: StorageProvider,
) -> list[CatalogMediaOut]:
    _get_item_or_404(db, workspace_id, item_id)
    rows = db.scalars(
        select(CatalogMedia)
        .where(
            CatalogMedia.item_id == item_id,
            CatalogMedia.workspace_id == workspace_id,
        )
        .order_by(
            CatalogMedia.is_primary.desc(),
            CatalogMedia.sort_order.asc(),
            CatalogMedia.created_at.asc(),
        )
    ).all()
    return [_attach_urls(m, storage) for m in rows]


def get_media_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    storage: StorageProvider,
) -> CatalogMediaOut:
    media = _get_media_or_404(db, workspace_id, item_id, media_id)
    return _attach_urls(media, storage)


def upload_media(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    file_data: bytes,
    filename: str,
    content_type: str,
    storage: StorageProvider,
    display_name: str | None = None,
    alt_text: str | None = None,
    is_primary: bool = False,
) -> CatalogMediaOut:
    _get_item_or_404(db, workspace_id, item_id)

    # ── Validate MIME type ────────────────────────────────────────────────────
    mime = content_type.split(";")[0].strip().lower()
    if mime not in _ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"File type not allowed: {mime!r}. "
                "Accepted types: JPEG, PNG, WebP, GIF, PDF."
            ),
        )

    # ── Validate size ─────────────────────────────────────────────────────────
    size = len(file_data)
    limit = _size_limit_for(mime)
    if size > limit:
        mb = limit / 1_048_576
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File too large. Maximum size for this type is {mb:.0f} MB.",
        )
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must not be empty.",
        )

    file_type = _derive_file_type(mime)
    media_id = uuid.uuid4()
    file_key = _build_key(workspace_id, item_id, media_id, filename)

    # ── Determine is_primary ──────────────────────────────────────────────────
    # Auto-primary: first image for this item → mark as primary.
    if file_type == "image":
        existing_images = db.scalar(
            select(CatalogMedia).where(
                CatalogMedia.item_id == item_id,
                CatalogMedia.workspace_id == workspace_id,
                CatalogMedia.file_type == "image",
            )
        )
        if existing_images is None:
            is_primary = True

    # Unset any previous primary if we're becoming the new one.
    if is_primary and file_type == "image":
        db.execute(
            update(CatalogMedia)
            .where(
                CatalogMedia.item_id == item_id,
                CatalogMedia.workspace_id == workspace_id,
                CatalogMedia.is_primary == True,  # noqa: E712
            )
            .values(is_primary=False, updated_at=datetime.now(timezone.utc))
        )

    media = CatalogMedia(
        id=media_id,
        workspace_id=workspace_id,
        item_id=item_id,
        file_key=file_key,
        original_filename=filename,
        display_name=display_name,
        mime_type=mime,
        file_type=file_type,
        size_bytes=size,
        sort_order=0,
        is_primary=is_primary if file_type == "image" else False,
        alt_text=alt_text,
        metadata_json={},
    )
    db.add(media)
    db.flush()  # get ID before storage write

    # ── Upload to storage ─────────────────────────────────────────────────────
    try:
        storage.put_file(file_key, file_data, content_type=mime)
    except StorageError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage error: {exc}",
        ) from exc

    db.commit()
    db.refresh(media)
    return _attach_urls(media, storage)


def update_media(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    data: CatalogMediaUpdate,
    storage: StorageProvider,
) -> CatalogMediaOut:
    media = _get_media_or_404(db, workspace_id, item_id, media_id)
    payload = data.model_dump(exclude_unset=True)
    if payload:
        for field, value in payload.items():
            setattr(media, field, value)
        media.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(media)
    return _attach_urls(media, storage)


def delete_media(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    storage: StorageProvider,
) -> None:
    media = _get_media_or_404(db, workspace_id, item_id, media_id)
    was_primary = media.is_primary
    file_key = media.file_key

    db.delete(media)
    db.flush()

    # If deleted media was primary image, promote next image alphabetically.
    if was_primary:
        next_image = db.scalar(
            select(CatalogMedia).where(
                CatalogMedia.item_id == item_id,
                CatalogMedia.workspace_id == workspace_id,
                CatalogMedia.file_type == "image",
            ).order_by(CatalogMedia.sort_order.asc(), CatalogMedia.created_at.asc())
        )
        if next_image is not None:
            next_image.is_primary = True
            next_image.updated_at = datetime.now(timezone.utc)

    db.commit()

    # Delete from storage after DB commit (best-effort; orphaned keys can be cleaned up).
    try:
        storage.delete_file(file_key)
    except StorageError:
        pass


def set_primary(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    media_id: uuid.UUID,
    storage: StorageProvider,
) -> CatalogMediaOut:
    media = _get_media_or_404(db, workspace_id, item_id, media_id)

    if media.file_type != "image":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only images can be set as primary.",
        )

    # Unset all other primaries.
    db.execute(
        update(CatalogMedia)
        .where(
            CatalogMedia.item_id == item_id,
            CatalogMedia.workspace_id == workspace_id,
            CatalogMedia.is_primary == True,  # noqa: E712
        )
        .values(is_primary=False, updated_at=datetime.now(timezone.utc))
    )
    media.is_primary = True
    media.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(media)
    return _attach_urls(media, storage)


def reorder_media(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    items: list[CatalogMediaReorderItem],
    storage: StorageProvider,
) -> list[CatalogMediaOut]:
    _get_item_or_404(db, workspace_id, item_id)

    media_ids = [i.id for i in items]
    rows = db.scalars(
        select(CatalogMedia).where(
            CatalogMedia.id.in_(media_ids),
            CatalogMedia.item_id == item_id,
            CatalogMedia.workspace_id == workspace_id,
        )
    ).all()

    if len(rows) != len(items):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="One or more media IDs not found in this item.",
        )

    by_id = {m.id: m for m in rows}
    now = datetime.now(timezone.utc)
    for item in items:
        by_id[item.id].sort_order = item.sort_order
        by_id[item.id].updated_at = now

    db.commit()
    return list_media(db, workspace_id, item_id, storage)


def get_storage_or_503() -> StorageProvider:
    """Return the configured storage provider, or raise 503 if misconfigured."""
    from app.services.storage.factory import get_storage_provider
    try:
        return get_storage_provider()
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Storage não configurado. Configure as variáveis R2 para enviar arquivos. ({exc})"
            ),
        ) from exc
