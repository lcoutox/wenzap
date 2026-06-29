import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Shared validators ─────────────────────────────────────────────────────────

def _validate_metadata(v: Any) -> dict:
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise ValueError("metadata_json must be a JSON object")
    return v


def _validate_tags(v: Any) -> list:
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError("tags must be a JSON array")
    return [str(t) for t in v]


# ── Category schemas ──────────────────────────────────────────────────────────

class CatalogCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    slug: str | None = Field(default=None, max_length=200)
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True


class CatalogCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    slug: str | None = Field(default=None, max_length=200)
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def name_cannot_be_null(self) -> "CatalogCategoryUpdate":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be set to null")
        return self


class CatalogCategoryOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    slug: str | None
    description: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Item schemas ──────────────────────────────────────────────────────────────

_VALID_ITEM_STATUSES = {"draft", "active", "inactive", "unavailable", "archived"}


class CatalogItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    category_id: uuid.UUID | None = None
    slug: str | None = Field(default=None, max_length=300)
    short_description: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    status: str = "active"
    tags: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    external_id: str | None = Field(default=None, max_length=200)
    sku: str | None = Field(default=None, max_length=200)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_featured: bool = False

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str) -> str:
        if v not in _VALID_ITEM_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_VALID_ITEM_STATUSES))}")
        return v

    @field_validator("metadata_json", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> dict:
        return _validate_metadata(v)

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: Any) -> list:
        return _validate_tags(v)


class CatalogItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    category_id: uuid.UUID | None = None
    slug: str | None = Field(default=None, max_length=300)
    short_description: str | None = None
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: str | None = None
    tags: list[str] | None = None
    metadata_json: dict[str, Any] | None = None
    external_id: str | None = Field(default=None, max_length=200)
    sku: str | None = Field(default=None, max_length=200)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_featured: bool | None = None

    @model_validator(mode="after")
    def name_cannot_be_null(self) -> "CatalogItemUpdate":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be set to null")
        return self

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_ITEM_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_VALID_ITEM_STATUSES))}")
        return v

    @field_validator("metadata_json", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> dict | None:
        if v is None:
            return None
        return _validate_metadata(v)

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: Any) -> list | None:
        if v is None:
            return None
        return _validate_tags(v)


# ── Media schemas ─────────────────────────────────────────────────────────────
# Defined before CatalogItemOut so it can be referenced as a forward field.

class CatalogMediaOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    item_id: uuid.UUID
    file_key: str
    original_filename: str
    display_name: str | None
    mime_type: str
    file_type: str
    size_bytes: int
    sort_order: int
    is_primary: bool
    alt_text: str | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime
    # Populated at serialisation time by the service layer.
    preview_url: str | None = None
    download_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CatalogMediaUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=300)
    alt_text: str | None = None
    sort_order: int | None = None
    metadata_json: dict | None = None

    @field_validator("metadata_json", mode="before")
    @classmethod
    def validate_metadata(cls, v: Any) -> dict | None:
        if v is None:
            return None
        return _validate_metadata(v)


class CatalogMediaReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int


# ── Item Out (after CatalogMediaOut so primary_media can reference it) ────────

class CatalogItemOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    category_id: uuid.UUID | None
    name: str
    slug: str | None
    short_description: str | None
    description: str | None
    price: float | None
    currency: str
    status: str
    tags: list[str]
    metadata_json: dict[str, Any]
    searchable_text: str | None
    external_id: str | None
    sku: str | None
    stock_quantity: int | None
    is_featured: bool
    created_at: datetime
    updated_at: datetime
    # Populated by the service layer when include_primary_media=true.
    primary_media: CatalogMediaOut | None = None

    model_config = ConfigDict(from_attributes=True)


# ── List filter params ────────────────────────────────────────────────────────

class CatalogItemFilters(BaseModel):
    q: str | None = None
    category_id: uuid.UUID | None = None
    status: str | None = None
    is_featured: bool | None = None
    has_price: bool | None = None
    tag: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    include_primary_media: bool = False


# ── Catalog Import ─────────────────────────────────────────────────────────────

class CatalogImportRowPreview(BaseModel):
    row_number: int
    values: dict[str, str]


class CatalogImportPreview(BaseModel):
    filename: str
    total_rows: int
    columns: list[str]
    rows_preview: list[CatalogImportRowPreview]
    warnings: list[str]


class CatalogImportError(BaseModel):
    row_number: int
    field: str | None
    message: str


class CatalogImportWarning(BaseModel):
    row_number: int | None
    message: str


class CatalogImportReport(BaseModel):
    total_rows: int
    created: int
    updated: int
    skipped: int
    errors: list[CatalogImportError]
    warnings: list[CatalogImportWarning]
