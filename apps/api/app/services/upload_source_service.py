"""
Upload source service — Phase 4.4.4.

Handles the full lifecycle of creating a KnowledgeSource from a file upload:
  1. Validate KB, plan limits, file size, and file type.
  2. Sanitise filename.
  3. Create KnowledgeSource (status=pending).
  4. Save the original file to storage.
  5. Extract text using the appropriate FileExtractor.
  6. Populate content_text and file metadata fields.
  7. Run the indexing pipeline (chunking + embeddings).
  8. Return the source (status=ready or status=failed).

On extraction/indexing failure the source is committed as failed — the original
file is preserved in storage to allow future re-extraction.

Reprocess (Phase 4.4) continues to use content_text already stored.
Re-extracting from the original file is planned for a future phase.
"""

import hashlib
import os
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.knowledge_source import KnowledgeSource
from app.services.embedding_providers.base import EmbeddingProvider
from app.services.file_extractors import ExtractionError, get_extractor
from app.services.indexing_service import IndexingError, index_source
from app.services.knowledge_source_service import (
    _check_source_limit,
    _get_kb_or_404,
    _get_workspace_plan,
)
from app.services.storage.base import StorageError, StorageProvider
from app.services.storage.factory import get_storage_provider

# ── File type registry ────────────────────────────────────────────────────────

# Maps (extension, frozenset of accepted MIME types) → source_type.
# Extension matching is case-insensitive and is authoritative; MIME is advisory.
_EXT_MAP: dict[str, tuple[frozenset[str], str]] = {
    ".txt": (frozenset({"text/plain"}), "txt"),
    ".md": (frozenset({"text/markdown", "text/plain"}), "markdown"),
    ".markdown": (frozenset({"text/markdown", "text/plain"}), "markdown"),
    ".pdf": (frozenset({"application/pdf"}), "pdf_simple"),
    ".csv": (frozenset({"text/csv", "application/csv", "text/plain"}), "csv_simple"),
}

_PDF_MAGIC = b"%PDF"

# ── Public API ────────────────────────────────────────────────────────────────


def upload_knowledge_source(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    file_data: bytes,
    filename: str,
    content_type: str | None,
    title: str | None = None,
    source_category: str | None = None,
    storage: StorageProvider | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> KnowledgeSource:
    """
    Create a KnowledgeSource from an uploaded file.

    Pre-creation errors raise HTTPException (4xx).
    Post-creation errors (extraction/indexing) return the source with status=failed.
    """
    # 1. Validate KB (raises 404 if not found/archived/cross-tenant).
    _get_kb_or_404(db, workspace_id, kb_id)

    # 2. Plan limits.
    plan = _get_workspace_plan(db, workspace_id)
    _check_source_limit(db, kb_id, plan)

    # 3. Validate file size.
    size_limit = (
        plan.max_file_size_bytes
        if plan and plan.max_file_size_bytes is not None
        else app_settings.max_file_size_bytes
    )
    if len(file_data) > size_limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"O tamanho do arquivo ({len(file_data):,} bytes) excede o limite de "
                f"{size_limit:,} bytes do seu plano."
            ),
        )

    # 4. Validate type (extension + MIME + magic bytes).
    safe_name = safe_filename(filename)
    ext = os.path.splitext(safe_name)[1].lower()

    if ext not in _EXT_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"O tipo de arquivo {ext!r} não é suportado. "
                f"Extensões aceitas: {', '.join(sorted(_EXT_MAP))}."
            ),
        )

    accepted_mimes, source_type = _EXT_MAP[ext]
    normalised_mime = (content_type or "").split(";")[0].strip().lower()
    if normalised_mime and normalised_mime not in accepted_mimes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"O tipo MIME {normalised_mime!r} não é aceito para arquivos {ext!r}. "
                f"Esperado um dos seguintes: {', '.join(sorted(accepted_mimes))}."
            ),
        )

    if ext == ".pdf" and not file_data.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O arquivo não parece ser um PDF válido (cabeçalho %PDF ausente).",
        )

    # 5. Resolve effective title.
    clean_title = title.strip() if title and title.strip() else None
    effective_title = clean_title or os.path.splitext(safe_name)[0]

    # 6. Content hash.
    content_hash = hashlib.sha256(file_data).hexdigest()

    # 7. Create source (status=pending).
    metadata_json: dict | None = (
        {"source_category": source_category} if source_category else None
    )
    source = KnowledgeSource(
        workspace_id=workspace_id,
        knowledge_base_id=kb_id,
        source_type=source_type,
        title=effective_title,
        content_text=None,
        status="pending",
        metadata_json=metadata_json,
        created_by_user_id=user_id,
        original_filename=safe_name,
        mime_type=normalised_mime or None,
        file_size_bytes=len(file_data),
        content_hash=content_hash,
    )
    db.add(source)
    db.flush()  # get source.id

    # 8. Storage key and save file.
    storage_key = (
        f"workspaces/{workspace_id}/knowledge-bases/{kb_id}"
        f"/sources/{source.id}/original/{safe_name}"
    )
    resolved_storage = storage or get_storage_provider()

    try:
        resolved_storage.put_file(storage_key, file_data, content_type=normalised_mime or None)
    except StorageError as exc:
        # Storage failure before content is extracted — abort cleanly.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro de armazenamento: {exc}",
        ) from exc

    source.storage_key = storage_key
    source.storage_provider = app_settings.storage_provider
    db.flush()

    # 9. Extract text.
    source.status = "processing"
    source.updated_at = datetime.now(timezone.utc)
    db.flush()

    try:
        extractor = get_extractor(source_type)
        extracted_text = extractor.extract(file_data)
    except ExtractionError as exc:
        _mark_failed(db, source, f"Extraction failed: {exc}")
        db.commit()
        db.refresh(source)
        return source

    source.content_text = extracted_text
    db.flush()

    # 10. Index (chunk + embed).
    try:
        index_source(db, source, provider=embedding_provider)
        db.commit()
    except IndexingError:
        db.commit()

    db.refresh(source)
    return source


# ── Helpers ───────────────────────────────────────────────────────────────────

_SAFE_CHAR_RE = re.compile(r"[^\w.\-]")


def safe_filename(filename: str) -> str:
    """
    Return a filesystem-safe version of *filename*.

    Rules:
    - Take only the basename (eliminates path traversal sequences).
    - Replace any character that isn't alphanumeric, '.', '-', or '_' with '_'.
    - Strip leading dots (avoids hidden files on Unix).
    - Truncate to 200 characters.
    - Fall back to "file" if the result is empty.
    """
    name = os.path.basename(filename)
    name = _SAFE_CHAR_RE.sub("_", name)
    name = name.lstrip(".")
    name = name[:200]
    return name or "file"


def _mark_failed(db: Session, source: KnowledgeSource, message: str) -> None:
    source.status = "failed"
    source.error_message = message[:500]
    source.updated_at = datetime.now(timezone.utc)
    db.flush()
