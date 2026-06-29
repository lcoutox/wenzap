"""
Catalog Embedding Service — Catálogo.4.

Generates and manages vector embeddings for catalog items.

Design decisions:
  - Follows the same pattern as indexing_service.py (Knowledge Base).
  - Embeddings stored directly in catalog_items (same as knowledge_chunks).
  - content_hash detects staleness: if hash matches, embedding is skipped.
  - Failure to embed never breaks create/update of an item.
  - Provider is optional: callers can pass a custom one for tests; None means
    the configured default (mock in dev/test, OpenAI in prod).
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog_category import CatalogCategory
from app.models.catalog_item import CatalogItem
from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider

logger = logging.getLogger(__name__)


# ── Content hash ──────────────────────────────────────────────────────────────

def compute_content_hash(item: CatalogItem, category_name: str | None) -> str:
    """
    Return a SHA-256 hex digest of the content fields that influence the embedding.

    If this hash matches item.content_hash, the embedding is still valid.
    """
    payload = {
        "name": item.name or "",
        "short_description": item.short_description or "",
        "description": (item.description or "")[:1000],
        "category": category_name or "",
        "price": str(item.price) if item.price is not None else "",
        "currency": item.currency or "",
        "tags": sorted(item.tags or []),
        "metadata_json": item.metadata_json or {},
        "searchable_text": item.searchable_text or "",
        "status": item.status or "",
    }
    content = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


# ── Embedding text builder ────────────────────────────────────────────────────

def build_embedding_text(item: CatalogItem, category_name: str | None) -> str:
    """
    Compose the text to embed for a catalog item.

    Combines the most descriptive fields into a single block that
    captures the item's identity and key attributes.
    """
    parts: list[str] = []
    if item.name:
        parts.append(f"Nome: {item.name}")
    if category_name:
        parts.append(f"Categoria: {category_name}")
    if item.short_description:
        parts.append(f"Descrição: {item.short_description}")
    if item.description:
        parts.append(f"Detalhes: {item.description[:500]}")
    if item.price is not None:
        parts.append(f"Preço: {item.price} {item.currency}")
    if item.tags:
        parts.append(f"Tags: {', '.join(item.tags)}")
    if item.metadata_json:
        meta_parts = [f"{k}: {v}" for k, v in list(item.metadata_json.items())[:8]]
        parts.append(f"Atributos: {', '.join(meta_parts)}")
    if item.searchable_text:
        parts.append(item.searchable_text)
    return "\n".join(parts)


def _resolve_category_name(db: Session, item: CatalogItem) -> str | None:
    if item.category_id is None:
        return None
    cat = db.scalar(
        select(CatalogCategory).where(CatalogCategory.id == item.category_id)
    )
    return cat.name if cat else None


# ── Single-item embedding ─────────────────────────────────────────────────────

def embed_catalog_item(
    db: Session,
    item: CatalogItem,
    provider: EmbeddingProvider | None = None,
    force: bool = False,
) -> bool:
    """
    Generate (or skip) the embedding for one catalog item.

    Parameters
    ----------
    db       : Active DB session. Caller commits.
    item     : The item to embed (must be attached to the session).
    provider : Optional provider override (primarily for tests).
    force    : If True, regenerate even when content_hash matches.

    Returns
    -------
    True if embedding was written, False if skipped (unchanged content or error).

    Never raises — embedding failures are logged and the item is left without
    an updated embedding so the lexical fallback can still be used.
    """
    from app.services.embedding_service import embed_texts

    try:
        category_name = _resolve_category_name(db, item)
        new_hash = compute_content_hash(item, category_name)

        if not force and item.content_hash == new_hash:
            return False  # Content unchanged — skip re-embedding.

        text = build_embedding_text(item, category_name)
        if not text.strip():
            return False

        result = embed_texts([text], provider=provider)
        embedding = result.embeddings[0]

        item.embedding = embedding
        item.embedding_provider = result.provider
        item.embedding_model = result.model
        item.embedding_dimension = result.dimension
        item.content_hash = new_hash
        item.embedded_at = datetime.now(timezone.utc)

        logger.debug(
            "catalog_item_embedded item_id=%s provider=%s model=%s",
            item.id, result.provider, result.model,
        )
        return True

    except EmbeddingError as exc:
        logger.warning(
            "catalog_item_embedding_skipped item_id=%s reason=%s",
            item.id, str(exc)[:200],
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "catalog_item_embedding_error item_id=%s error=%s",
            item.id, str(exc)[:200],
        )
        return False


# ── Backfill ──────────────────────────────────────────────────────────────────

def embed_missing_for_workspace(
    db: Session,
    workspace_id: uuid.UUID,
    provider: EmbeddingProvider | None = None,
) -> dict:
    """
    Generate embeddings for all active items in a workspace that lack one
    or whose content_hash is stale.

    Returns a summary dict: {"processed": N, "skipped": N, "errors": N}.
    Commits after each item so a mid-batch failure doesn't lose prior work.
    """
    items = db.scalars(
        select(CatalogItem).where(
            CatalogItem.workspace_id == workspace_id,
            CatalogItem.status == "active",
        )
    ).all()

    processed = 0
    skipped = 0

    for item in items:
        wrote = embed_catalog_item(db, item, provider=provider)
        if wrote:
            db.commit()
            processed += 1
        else:
            skipped += 1

    logger.info(
        "catalog_backfill_done workspace=%s processed=%d skipped=%d",
        workspace_id, processed, skipped,
    )
    return {"processed": processed, "skipped": skipped}
