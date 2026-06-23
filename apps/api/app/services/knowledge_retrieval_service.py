"""
Knowledge retrieval service — Phase 4.2.4.

Basic vector similarity search using pgvector cosine distance.

This service receives a ready-made query embedding (list[float]) and returns
the most similar chunks from the specified knowledge bases.  It does NOT call
any embedding provider — that responsibility belongs to the caller (Phase 4.3).

Scoring:
    score = 1 - cosine_distance   (higher = more similar)
    rank  = 1-based position in the ordered result list
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_source import KnowledgeSource


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_id: uuid.UUID
    content: str
    score: float
    rank: int
    metadata: dict[str, Any] | None


def search_similar_chunks(
    db: Session,
    workspace_id: uuid.UUID,
    knowledge_base_ids: list[uuid.UUID],
    query_embedding: list[float],
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """
    Return the top-k chunks most similar to *query_embedding* from the given KBs.

    Guards:
    - Returns [] if knowledge_base_ids is empty.
    - Returns [] if top_k <= 0.
    - Always scopes to workspace_id.
    - Only considers chunks whose source has status = "ready".
    - Skips chunks from archived sources or archived KBs.

    Parameters
    ----------
    workspace_id        : Tenant scope — enforced in every query.
    knowledge_base_ids  : Which KBs to search (must belong to workspace_id).
    query_embedding     : Pre-computed embedding of the search query.
    top_k               : Maximum number of chunks to return.
    """
    if not knowledge_base_ids or top_k <= 0:
        return []

    distance_col = KnowledgeChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(KnowledgeChunk, distance_col.label("distance"))
        .join(KnowledgeSource, KnowledgeChunk.source_id == KnowledgeSource.id)
        .join(KnowledgeBase, KnowledgeChunk.knowledge_base_id == KnowledgeBase.id)
        .where(
            KnowledgeChunk.workspace_id == workspace_id,
            KnowledgeChunk.knowledge_base_id.in_(knowledge_base_ids),
            KnowledgeSource.status == "ready",
            KnowledgeSource.workspace_id == workspace_id,
            KnowledgeBase.status != "archived",
            KnowledgeBase.workspace_id == workspace_id,
        )
        .order_by(distance_col.asc())
        .limit(top_k)
    )

    rows = db.execute(stmt).all()

    results: list[RetrievedChunk] = []
    for rank, (chunk, distance) in enumerate(rows, start=1):
        results.append(
            RetrievedChunk(
                chunk_id=chunk.id,
                workspace_id=chunk.workspace_id,
                knowledge_base_id=chunk.knowledge_base_id,
                source_id=chunk.source_id,
                content=chunk.content,
                score=float(1.0 - distance),
                rank=rank,
                metadata=chunk.metadata_json,
            )
        )

    return results
