"""
Catalog Import Service — Catálogo.8.

Supports CSV and XLSX import for CatalogItem data.
Two-step flow:
  1. preview()  — parse file, return detected columns + row preview
  2. commit()   — reparse file + mapping, create/update items, return report
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog_category import CatalogCategory
from app.models.catalog_item import CatalogItem
from app.services.catalog_service import _try_embed_item, build_searchable_text

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 2_000
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Columns that carry image/media URLs — warn, do not import value
_IMAGE_COLUMN_HINTS = {
    "image", "imagem", "foto", "photo", "picture", "img",
    "image_url", "foto_url", "imagem_url", "photo_url",
}

ImportMode = Literal["create_only", "upsert_by_sku", "upsert_by_external_id"]


# ── Data containers ───────────────────────────────────────────────────────────

@dataclass
class RowPreview:
    row_number: int
    values: dict[str, str]


@dataclass
class ImportPreview:
    filename: str
    total_rows: int
    columns: list[str]
    rows_preview: list[RowPreview]
    warnings: list[str]


@dataclass
class ImportError:
    row_number: int
    field: str | None
    message: str


@dataclass
class ImportWarning:
    row_number: int | None
    message: str


@dataclass
class ImportReport:
    total_rows: int
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[ImportError] = field(default_factory=list)
    warnings: list[ImportWarning] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────

async def preview(upload: UploadFile) -> ImportPreview:
    content, filename, ext = await _read_and_validate(upload)
    rows = _parse_file(content, ext)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O arquivo não contém linhas de dados.",
        )

    columns = list(rows[0].keys())
    warnings: list[str] = []

    for col in columns:
        if col.lower().strip() in _IMAGE_COLUMN_HINTS:
            warnings.append(
                f"A coluna '{col}' parece conter URL de imagem. "
                "A importação de imagens não é suportada nesta versão — "
                "adicione imagens pela tela de cada item."
            )

    preview_rows = [
        RowPreview(row_number=i + 2, values=row)
        for i, row in enumerate(rows[:5])
    ]

    return ImportPreview(
        filename=filename,
        total_rows=len(rows),
        columns=columns,
        rows_preview=preview_rows,
        warnings=warnings,
    )


async def commit(
    db: Session,
    workspace_id: uuid.UUID,
    upload: UploadFile,
    mapping: dict,
    mode: ImportMode,
) -> ImportReport:
    _validate_mode_mapping(mode, mapping)

    content, _, ext = await _read_and_validate(upload)
    rows = _parse_file(content, ext)

    report = ImportReport(total_rows=len(rows))
    meta_mapping: dict[str, str] = mapping.get("metadata", {}) or {}

    # Detect image-column warnings once
    all_columns = set(rows[0].keys()) if rows else set()
    for col in all_columns:
        if col.lower().strip() in _IMAGE_COLUMN_HINTS:
            report.warnings.append(ImportWarning(
                row_number=None,
                message=(
                    f"Coluna '{col}' ignorada: importação de imagens não suportada nesta versão."
                ),
            ))

    for i, row in enumerate(rows):
        row_num = i + 2  # header is row 1
        try:
            _process_row(db, workspace_id, row, row_num, mapping, meta_mapping, mode, report)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(ImportError(
                row_number=row_num,
                field=None,
                message=f"Erro inesperado: {exc!s}",
            ))
            report.skipped += 1

    return report


# ── Row processing ────────────────────────────────────────────────────────────

def _process_row(
    db: Session,
    workspace_id: uuid.UUID,
    row: dict[str, str],
    row_num: int,
    mapping: dict,
    meta_mapping: dict[str, str],
    mode: ImportMode,
    report: ImportReport,
) -> None:
    name_col = mapping.get("name")
    name = _cell(row, name_col).strip()
    if not name:
        report.errors.append(ImportError(
            row_number=row_num,
            field="name",
            message="Campo 'nome' obrigatório está vazio.",
        ))
        report.skipped += 1
        return

    # Price
    price: Decimal | None = None
    price_col = mapping.get("price")
    if price_col:
        raw_price = _cell(row, price_col)
        if raw_price:
            parsed = _parse_price(raw_price)
            if parsed is None:
                report.errors.append(ImportError(
                    row_number=row_num,
                    field="price",
                    message=f"Preço inválido: '{raw_price}'.",
                ))
                report.skipped += 1
                return
            price = parsed

    # Status
    status_col = mapping.get("status")
    item_status = _parse_status(_cell(row, status_col)) if status_col else "active"

    # Tags
    tags_col = mapping.get("tags")
    tags: list[str] = _parse_tags(_cell(row, tags_col)) if tags_col else []

    # Category
    category_col = mapping.get("category")
    category_id: uuid.UUID | None = None
    if category_col:
        cat_name = _cell(row, category_col).strip()
        if cat_name:
            category_id = _get_or_create_category(db, workspace_id, cat_name)

    # Scalar text fields
    short_desc = _cell(row, mapping.get("short_description")) or None
    description = _cell(row, mapping.get("description")) or None
    sku = _cell(row, mapping.get("sku")) or None
    external_id = _cell(row, mapping.get("external_id")) or None
    currency = _cell(row, mapping.get("currency")) or "BRL"

    stock_qty: int | None = None
    sq_col = mapping.get("stock_quantity")
    if sq_col:
        raw_sq = _cell(row, sq_col)
        if raw_sq:
            try:
                stock_qty = int(float(raw_sq.replace(",", ".")))
            except (ValueError, TypeError):
                pass

    is_featured_col = mapping.get("is_featured")
    is_featured = False
    if is_featured_col:
        is_featured = _cell(row, is_featured_col).lower().strip() in {
            "1", "true", "yes", "sim", "verdadeiro",
        }

    # Extra metadata columns
    metadata_json: dict = {}
    for meta_key, col_name in meta_mapping.items():
        val = _cell(row, col_name).strip()
        if val:
            metadata_json[meta_key] = val

    # Upsert lookup
    existing: CatalogItem | None = None
    if mode == "upsert_by_sku" and sku:
        existing = db.scalar(
            select(CatalogItem).where(
                CatalogItem.workspace_id == workspace_id,
                CatalogItem.sku == sku,
            )
        )
    elif mode == "upsert_by_external_id" and external_id:
        existing = db.scalar(
            select(CatalogItem).where(
                CatalogItem.workspace_id == workspace_id,
                CatalogItem.external_id == external_id,
            )
        )

    if existing:
        existing.name = name
        existing.short_description = short_desc
        existing.description = description
        existing.price = price
        existing.currency = currency
        existing.status = item_status
        existing.tags = tags
        existing.sku = sku
        existing.external_id = external_id
        existing.stock_quantity = stock_qty
        existing.is_featured = is_featured
        existing.category_id = category_id
        if metadata_json:
            existing.metadata_json = {**(existing.metadata_json or {}), **metadata_json}
        category_name = _resolve_category_name(db, category_id)
        existing.searchable_text = build_searchable_text(existing, category_name)
        db.commit()
        db.refresh(existing)
        _try_embed_item(db, existing)
        report.updated += 1
    else:
        item = CatalogItem(
            workspace_id=workspace_id,
            category_id=category_id,
            name=name,
            short_description=short_desc,
            description=description,
            price=price,
            currency=currency,
            status=item_status,
            tags=tags,
            metadata_json=metadata_json or None,
            external_id=external_id,
            sku=sku,
            stock_quantity=stock_qty,
            is_featured=is_featured,
        )
        db.add(item)
        db.flush()
        category_name = _resolve_category_name(db, category_id)
        item.searchable_text = build_searchable_text(item, category_name)
        db.commit()
        db.refresh(item)
        _try_embed_item(db, item)
        report.created += 1


# ── File I/O ──────────────────────────────────────────────────────────────────

async def _read_and_validate(upload: UploadFile) -> tuple[bytes, str, str]:
    content = await upload.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="O arquivo excede o limite de 5 MB. Divida em arquivos menores.",
        )

    filename = upload.filename or "upload"
    ext = _file_ext(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Formato não suportado: '{ext}'. Use CSV ou XLSX.",
        )

    return content, filename, ext


def _parse_file(content: bytes, ext: str) -> list[dict[str, str]]:
    if ext == ".csv":
        return _parse_csv(content)
    return _parse_xlsx(content)


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for row in reader:
        rows.append({k: (v or "") for k, v in row.items() if k is not None})
        if len(rows) >= MAX_ROWS:
            break
    return rows


def _parse_xlsx(content: bytes) -> list[dict[str, str]]:
    import openpyxl  # noqa: PLC0415

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return []

    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        return []

    headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(header_row)]

    rows: list[dict[str, str]] = []
    for raw_row in rows_iter:
        row: dict[str, str] = {}
        for h, val in zip(headers, raw_row):
            row[h] = str(val).strip() if val is not None else ""
        rows.append(row)
        if len(rows) >= MAX_ROWS:
            break

    wb.close()
    return rows


# ── Value normalization ───────────────────────────────────────────────────────

def _parse_price(raw: str) -> Decimal | None:
    cleaned = raw.strip()
    cleaned = re.sub(r"[R$\s]", "", cleaned)
    # Handle Brazilian format: 88.900,00 → 88900.00
    if re.search(r"\d+\.\d{3},", cleaned):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


_STATUS_MAP = {
    "active": "active", "ativo": "active", "ativa": "active",
    "draft": "draft", "rascunho": "draft",
    "inactive": "inactive", "inativo": "inactive", "inativa": "inactive",
    "unavailable": "unavailable", "indisponível": "unavailable", "indisponivel": "unavailable",
    "archived": "archived", "arquivado": "archived", "arquivada": "archived",
}


def _parse_status(raw: str) -> str:
    return _STATUS_MAP.get(raw.lower().strip(), "active")


def _parse_tags(raw: str) -> list[str]:
    parts = re.split(r"[,;|]", raw)
    return [p.strip() for p in parts if p.strip()]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cell(row: dict[str, str], col: str | None) -> str:
    if not col:
        return ""
    return row.get(col, "") or ""


def _file_ext(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return ".xlsx"
    if lower.endswith(".xls"):
        return ".xls"
    if lower.endswith(".csv"):
        return ".csv"
    return ""


def _get_or_create_category(
    db: Session,
    workspace_id: uuid.UUID,
    name: str,
) -> uuid.UUID:
    existing = db.scalar(
        select(CatalogCategory).where(
            CatalogCategory.workspace_id == workspace_id,
            CatalogCategory.name == name,
        )
    )
    if existing:
        return existing.id
    cat = CatalogCategory(
        workspace_id=workspace_id,
        name=name,
        slug=_slugify(name),
        is_active=True,
        sort_order=0,
    )
    db.add(cat)
    db.flush()
    return cat.id


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[àáâãä]", "a", slug)
    slug = re.sub(r"[èéêë]", "e", slug)
    slug = re.sub(r"[ìíîï]", "i", slug)
    slug = re.sub(r"[òóôõö]", "o", slug)
    slug = re.sub(r"[ùúûü]", "u", slug)
    slug = re.sub(r"[ç]", "c", slug)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug[:100]


def _resolve_category_name(db: Session, category_id: uuid.UUID | None) -> str | None:
    if category_id is None:
        return None
    cat = db.get(CatalogCategory, category_id)
    return cat.name if cat else None


def _validate_mode_mapping(mode: ImportMode, mapping: dict) -> None:
    if mode == "upsert_by_sku" and not mapping.get("sku"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Modo 'upsert_by_sku' requer que a coluna 'sku' esteja mapeada.",
        )
    if mode == "upsert_by_external_id" and not mapping.get("external_id"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Modo 'upsert_by_external_id' requer que a coluna 'external_id' esteja mapeada.",
        )
