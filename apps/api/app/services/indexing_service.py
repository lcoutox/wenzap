"""
Indexing service — Phase 4.2.3.

Transforms a KnowledgeSource into KnowledgeChunk rows with embeddings.
No HTTP concerns: raises IndexingError on failure so callers can decide how
to surface the error (create_source returns 201 with status="failed").
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete as sql_delete
from sqlalchemy.orm import Session

from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_source import KnowledgeSource
from app.services.chunking_service import chunk_source_content
from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider
from app.services.embedding_service import embed_texts


class IndexingError(Exception):
    """Raised when indexing a source fails (chunking, embedding, or DB error)."""


def delete_source_chunks(db: Session, source_id: uuid.UUID) -> None:
    """Hard-delete all KnowledgeChunk rows for the given source."""
    db.execute(sql_delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id))


def index_source(
    db: Session,
    source: KnowledgeSource,
    provider: EmbeddingProvider | None = None,
) -> list[KnowledgeChunk]:
    """
    Index a KnowledgeSource: chunk → embed → persist chunks → mark ready.

    Flow:
    1. Delete any existing chunks for this source.
    2. Generate chunk data (in memory, no DB writes yet).
    3. Fail fast if no chunks were produced.
    4. Generate ALL embeddings in memory (before any DB write), so a provider
       failure leaves the DB in a clean state.
    5. Persist chunks.
    6. Mark source as ready.

    On any failure:
    - Deletes any partial chunks that may have been added.
    - Sets source.status = "failed" and source.error_message.
    - Raises IndexingError so the caller can commit the failed state.
    """
    now = datetime.now(timezone.utc)

    # 1. Remove stale chunks (idempotent for reprocess later)
    delete_source_chunks(db, source.id)
    db.flush()

    try:
        # 2. Chunk (faq_qa uses min_chunk_chars=1 so short valid pairs are kept)
        min_chunk_chars = 1 if source.source_type == "faq_qa" else 50
        chunks_data = chunk_source_content(
            source_type=source.source_type,
            content_text=source.content_text,
            metadata_json=source.metadata_json,
            min_chunk_chars=min_chunk_chars,
        )

        # 3. Fail if no chunks
        if not chunks_data:
            raise IndexingError(
                "No content could be extracted from this source. "
                "Ensure the source has non-empty content."
            )

        # 4. Generate ALL embeddings before writing anything to DB.
        texts = [c.content for c in chunks_data]
        result = embed_texts(texts, provider=provider)

        # 5. Persist chunks
        db_chunks: list[KnowledgeChunk] = []
        for chunk_data, embedding in zip(chunks_data, result.embeddings):
            chunk = KnowledgeChunk(
                workspace_id=source.workspace_id,
                knowledge_base_id=source.knowledge_base_id,
                source_id=source.id,
                chunk_index=chunk_data.chunk_index,
                content=chunk_data.content,
                char_count=chunk_data.char_count,
                metadata_json=chunk_data.metadata,
                embedding=embedding,
                embedding_provider=result.provider,
                embedding_model=result.model,
                embedding_dimension=result.dimension,
                updated_at=now,
            )
            db.add(chunk)
            db_chunks.append(chunk)

        # 6. Mark source ready
        source.status = "ready"
        source.error_message = None
        source.processed_at = now
        source.updated_at = now

        db.flush()
        return db_chunks

    except IndexingError as exc:
        # Re-raise after cleaning up; caller will commit the failed state.
        _mark_failed(db, source, _truncate(str(exc)))
        raise

    except EmbeddingError as exc:
        delete_source_chunks(db, source.id)
        _mark_failed(db, source, f"Embedding failed: {_truncate(str(exc))}")
        raise IndexingError(str(exc)) from exc

    except Exception as exc:
        delete_source_chunks(db, source.id)
        _mark_failed(db, source, f"Indexing error: {_truncate(str(exc))}")
        raise IndexingError(str(exc)) from exc


# ── Private helpers ───────────────────────────────────────────────────────────

def _mark_failed(db: Session, source: KnowledgeSource, message: str) -> None:
    source.status = "failed"
    source.error_message = message[:500]
    source.updated_at = datetime.now(timezone.utc)
    db.flush()


def _truncate(s: str, max_len: int = 400) -> str:
    return s if len(s) <= max_len else s[:max_len] + "…"
