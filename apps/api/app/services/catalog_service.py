"""
Catalog service — CRUD for CatalogCategory and CatalogItem.

Workspace isolation is enforced at every query. Items with status="archived"
are excluded from list/get by default (hard-delete is not used).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.catalog_category import CatalogCategory
from app.models.catalog_item import CatalogItem
from app.models.catalog_media import CatalogMedia
from app.schemas.catalog import (
    CatalogCategoryCreate,
    CatalogCategoryUpdate,
    CatalogItemCreate,
    CatalogItemFilters,
    CatalogItemOut,
    CatalogItemUpdate,
    CatalogMediaOut,
)

# ── searchable_text generator ─────────────────────────────────────────────────

def build_searchable_text(
    item: CatalogItem,
    category_name: str | None = None,
) -> str:
    """
    Generate a denormalised plain-text representation of a catalog item
    for simple text search and future AI retrieval (Catálogo.3).

    Format:
      {name}. {short_description}. {description}. {category}. {price} {currency}.
      Tags: {tags}. {sku}. {external_id}. {metadata key=value pairs}.
    """
    parts: list[str] = []

    if item.name:
        parts.append(item.name)

    if item.short_description:
        parts.append(item.short_description)

    if item.description:
        parts.append(item.description)

    if category_name:
        parts.append(f"Categoria: {category_name}")

    if item.price is not None:
        raw = f"{Decimal(str(item.price)):,.2f}"
        price_str = raw.replace(",", "X").replace(".", ",").replace("X", ".")
        prefix = "R$" if item.currency == "BRL" else item.currency
        parts.append(f"{prefix} {price_str}")

    if item.tags:
        parts.append(f"Tags: {', '.join(item.tags)}")

    if item.sku:
        parts.append(f"SKU: {item.sku}")

    if item.external_id:
        parts.append(f"Ref: {item.external_id}")

    if item.metadata_json:
        meta_parts = [f"{k}: {v}" for k, v in item.metadata_json.items()]
        parts.append(". ".join(meta_parts))

    return ". ".join(p.strip().rstrip(".") for p in parts if p and p.strip())


# ── Category CRUD ─────────────────────────────────────────────────────────────

def list_categories(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    include_inactive: bool = False,
) -> list[CatalogCategory]:
    q = select(CatalogCategory).where(CatalogCategory.workspace_id == workspace_id)
    if not include_inactive:
        q = q.where(CatalogCategory.is_active == True)  # noqa: E712
    q = q.order_by(CatalogCategory.sort_order, CatalogCategory.name)
    return list(db.scalars(q).all())


def get_category_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
) -> CatalogCategory:
    cat = db.scalar(
        select(CatalogCategory).where(
            CatalogCategory.id == category_id,
            CatalogCategory.workspace_id == workspace_id,
        )
    )
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
    return cat


def create_category(
    db: Session,
    workspace_id: uuid.UUID,
    data: CatalogCategoryCreate,
) -> CatalogCategory:
    if data.parent_id is not None:
        get_category_or_404(db, workspace_id, data.parent_id)

    cat = CatalogCategory(
        workspace_id=workspace_id,
        parent_id=data.parent_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def update_category(
    db: Session,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
    data: CatalogCategoryUpdate,
) -> CatalogCategory:
    cat = get_category_or_404(db, workspace_id, category_id)
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        return cat

    if "parent_id" in payload and payload["parent_id"] is not None:
        if payload["parent_id"] == category_id:
            raise HTTPException(status_code=400, detail="A category cannot be its own parent.")
        get_category_or_404(db, workspace_id, payload["parent_id"])

    for field, value in payload.items():
        setattr(cat, field, value)

    cat.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(
    db: Session,
    workspace_id: uuid.UUID,
    category_id: uuid.UUID,
) -> CatalogCategory:
    """Soft-delete: sets is_active=False. Items keep category_id but category is hidden."""
    cat = get_category_or_404(db, workspace_id, category_id)
    cat.is_active = False
    cat.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cat)
    return cat


# ── Item CRUD ─────────────────────────────────────────────────────────────────

def _resolve_category_name(db: Session, category_id: uuid.UUID | None) -> str | None:
    if category_id is None:
        return None
    cat = db.scalar(select(CatalogCategory).where(CatalogCategory.id == category_id))
    return cat.name if cat else None


def list_items(
    db: Session,
    workspace_id: uuid.UUID,
    filters: CatalogItemFilters,
    storage=None,
) -> list[CatalogItemOut]:
    q = select(CatalogItem).where(
        CatalogItem.workspace_id == workspace_id,
        CatalogItem.status != "archived",
    )

    if filters.category_id is not None:
        q = q.where(CatalogItem.category_id == filters.category_id)

    if filters.status is not None:
        q = q.where(CatalogItem.status == filters.status)

    if filters.is_featured is not None:
        q = q.where(CatalogItem.is_featured == filters.is_featured)

    if filters.has_price is True:
        q = q.where(CatalogItem.price.isnot(None))
    elif filters.has_price is False:
        q = q.where(CatalogItem.price.is_(None))

    if filters.tag is not None:
        q = q.where(CatalogItem.tags.contains([filters.tag]))

    if filters.q:
        term = f"%{filters.q}%"
        q = q.where(
            or_(
                CatalogItem.name.ilike(term),
                CatalogItem.short_description.ilike(term),
                CatalogItem.description.ilike(term),
                CatalogItem.searchable_text.ilike(term),
                CatalogItem.sku.ilike(term),
                CatalogItem.external_id.ilike(term),
            )
        )

    q = q.order_by(CatalogItem.created_at.desc()).offset(filters.offset).limit(filters.limit)
    items = list(db.scalars(q).all())

    if not filters.include_primary_media or not items:
        return [CatalogItemOut.model_validate(item) for item in items]

    # Bulk-fetch primary media for all returned item IDs — 1 extra query, not N.
    item_ids = [item.id for item in items]
    primary_rows = db.scalars(
        select(CatalogMedia).where(
            CatalogMedia.item_id.in_(item_ids),
            CatalogMedia.workspace_id == workspace_id,
            CatalogMedia.is_primary == True,  # noqa: E712
            CatalogMedia.file_type == "image",
        )
    ).all()

    # Build lookup: item_id → CatalogMediaOut with URL
    primary_by_item: dict[uuid.UUID, CatalogMediaOut] = {}
    for media in primary_rows:
        out = CatalogMediaOut.model_validate(media)
        if storage is not None:
            try:
                url = storage.generate_presigned_url(media.file_key)
                out.preview_url = url
                out.download_url = url
            except Exception:
                pass
        primary_by_item[media.item_id] = out

    result: list[CatalogItemOut] = []
    for item in items:
        item_out = CatalogItemOut.model_validate(item)
        item_out.primary_media = primary_by_item.get(item.id)
        result.append(item_out)
    return result


def get_item_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
) -> CatalogItem:
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


def create_item(
    db: Session,
    workspace_id: uuid.UUID,
    data: CatalogItemCreate,
) -> CatalogItem:
    if data.category_id is not None:
        get_category_or_404(db, workspace_id, data.category_id)

    item = CatalogItem(
        workspace_id=workspace_id,
        category_id=data.category_id,
        name=data.name,
        slug=data.slug,
        short_description=data.short_description,
        description=data.description,
        price=data.price,
        currency=data.currency,
        status=data.status,
        tags=data.tags,
        metadata_json=data.metadata_json,
        external_id=data.external_id,
        sku=data.sku,
        stock_quantity=data.stock_quantity,
        is_featured=data.is_featured,
    )
    db.add(item)
    db.flush()

    category_name = _resolve_category_name(db, data.category_id)
    item.searchable_text = build_searchable_text(item, category_name)

    db.commit()
    db.refresh(item)

    # Silently generate embedding after commit — never breaks item creation.
    _try_embed_item(db, item)

    return item


def update_item(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
    data: CatalogItemUpdate,
) -> CatalogItem:
    item = get_item_or_404(db, workspace_id, item_id)
    payload = data.model_dump(exclude_unset=True)
    if not payload:
        return item

    if "category_id" in payload and payload["category_id"] is not None:
        get_category_or_404(db, workspace_id, payload["category_id"])

    for field, value in payload.items():
        setattr(item, field, value)

    item.updated_at = datetime.now(timezone.utc)

    category_name = _resolve_category_name(db, item.category_id)
    item.searchable_text = build_searchable_text(item, category_name)

    db.commit()
    db.refresh(item)

    # Silently refresh embedding if content changed — never breaks update.
    _try_embed_item(db, item)

    return item


def archive_item(
    db: Session,
    workspace_id: uuid.UUID,
    item_id: uuid.UUID,
) -> CatalogItem:
    item = get_item_or_404(db, workspace_id, item_id)
    item.status = "archived"
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


# ── Embedding helper ──────────────────────────────────────────────────────────

def _try_embed_item(db: Session, item: CatalogItem) -> None:
    """Generate/update embedding for *item* silently. Never raises."""
    try:
        from app.services.catalog_embedding_service import embed_catalog_item
        wrote = embed_catalog_item(db, item)
        if wrote:
            db.commit()
    except Exception:  # noqa: BLE001
        pass
