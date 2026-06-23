"""
Knowledge retrieval service — Phase 4.2.4 / 4.3.1.

Phase 4.2.4: Basic vector similarity search using pgvector cosine distance.
Phase 4.3.1: High-level `retrieve_context_for_agent` that resolves KB connections,
             embeds the query, and returns a structured RetrievalResult.

Scoring:
    score = 1 - cosine_distance   (higher = more similar)
    rank  = 1-based position in the ordered result list
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_knowledge_base import AgentKnowledgeBase
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_source import KnowledgeSource
from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID | None  # None only in tests/fake results; real retrievals always have an ID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_id: uuid.UUID
    content: str
    score: float
    rank: int
    metadata: dict[str, Any] | None


@dataclass
class RetrievalResult:
    """
    Outcome of a retrieval attempt for a given agent + query.

    Fields
    ------
    chunks               : Ordered list of retrieved chunks (empty if none found).
    retrieval_attempted  : True when at least one active KB was connected and the
                           system attempted to embed the query and search.
                           False when there are no active KBs or the query was empty.
    rag_used             : True when at least one chunk was successfully retrieved
                           (raw, before injection filtering). The service layer
                           (agent_test_service) computes the definitive rag_used
                           flag after applying injection filter and context limit.
    retrieval_duration_ms: Wall-clock time of the retrieval attempt in milliseconds.
    knowledge_base_ids   : IDs of the KBs that were searched (may be empty).
    error_message        : Set when an exception occurred during embedding or search.
                           The Playground must NOT propagate this as an HTTP error.
    """

    chunks: list[RetrievedChunk]
    retrieval_attempted: bool
    rag_used: bool
    retrieval_duration_ms: int
    knowledge_base_ids: list[uuid.UUID] = field(default_factory=list)
    error_message: str | None = None


# ── High-level agent retrieval ────────────────────────────────────────────────

def retrieve_context_for_agent(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    query: str,
    top_k: int | None = None,
    provider: EmbeddingProvider | None = None,
) -> RetrievalResult:
    """
    Retrieve relevant chunks for an agent given a user query.

    Flow
    ----
    1. Resolve active KB connections for the agent (within workspace_id).
    2. Return early if no active KBs are connected, or query is blank.
    3. Embed the query using *provider* (or the settings default).
    4. Search for similar chunks via pgvector cosine distance.
    5. Return a RetrievalResult; never raises — errors are captured in
       result.error_message so the Playground can degrade gracefully.

    Parameters
    ----------
    db           : Database session.
    workspace_id : Tenant scope — enforced on every query.
    agent_id     : The agent whose connected KBs will be searched.
    query        : Raw user message text (will be stripped internally).
    top_k        : Max chunks to return. Defaults to settings.rag_top_k.
    provider     : Optional embedding provider override (primarily for tests).
    """
    from app.config import settings

    resolved_top_k = top_k if top_k is not None else settings.rag_top_k

    t_start = time.monotonic()

    # 1. Resolve active KB connections scoped to this workspace.
    kb_ids = _get_active_kb_ids(db, workspace_id, agent_id)

    if not kb_ids:
        return RetrievalResult(
            chunks=[],
            retrieval_attempted=False,
            rag_used=False,
            retrieval_duration_ms=_elapsed_ms(t_start),
            knowledge_base_ids=[],
        )

    # 2. Guard: blank query → no retrieval attempt.
    clean_query = query.strip()
    if not clean_query:
        return RetrievalResult(
            chunks=[],
            retrieval_attempted=False,
            rag_used=False,
            retrieval_duration_ms=_elapsed_ms(t_start),
            knowledge_base_ids=kb_ids,
        )

    # 3. Guard: non-positive top_k → mark attempted (KBs exist) but return empty.
    if resolved_top_k <= 0:
        return RetrievalResult(
            chunks=[],
            retrieval_attempted=True,
            rag_used=False,
            retrieval_duration_ms=_elapsed_ms(t_start),
            knowledge_base_ids=kb_ids,
        )

    # 4. Embed + search — capture any failure without propagating.
    try:
        from app.services.embedding_service import embed_texts

        embed_result = embed_texts([clean_query], provider=provider)
        query_embedding = embed_result.embeddings[0]

        chunks = search_similar_chunks(
            db,
            workspace_id=workspace_id,
            knowledge_base_ids=kb_ids,
            query_embedding=query_embedding,
            top_k=resolved_top_k,
        )
    except EmbeddingError as exc:
        return RetrievalResult(
            chunks=[],
            retrieval_attempted=True,
            rag_used=False,
            retrieval_duration_ms=_elapsed_ms(t_start),
            knowledge_base_ids=kb_ids,
            error_message=str(exc)[:500],
        )
    except Exception as exc:  # noqa: BLE001
        return RetrievalResult(
            chunks=[],
            retrieval_attempted=True,
            rag_used=False,
            retrieval_duration_ms=_elapsed_ms(t_start),
            knowledge_base_ids=kb_ids,
            error_message=f"Retrieval error: {str(exc)[:480]}",
        )

    return RetrievalResult(
        chunks=chunks,
        retrieval_attempted=True,
        rag_used=len(chunks) > 0,
        retrieval_duration_ms=_elapsed_ms(t_start),
        knowledge_base_ids=kb_ids,
    )


# ── Low-level similarity search ───────────────────────────────────────────────

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


# ── Private helpers ───────────────────────────────────────────────────────────

def _get_active_kb_ids(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> list[uuid.UUID]:
    """
    Return the IDs of KBs that are actively connected to the agent and have
    status="active".  Scoped to workspace_id on both the connection and the KB.
    """
    rows = db.execute(
        select(AgentKnowledgeBase.knowledge_base_id)
        .join(
            KnowledgeBase,
            AgentKnowledgeBase.knowledge_base_id == KnowledgeBase.id,
        )
        .where(
            AgentKnowledgeBase.workspace_id == workspace_id,
            AgentKnowledgeBase.agent_id == agent_id,
            AgentKnowledgeBase.is_active == True,  # noqa: E712
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.status == "active",
        )
    ).all()
    return [row[0] for row in rows]


def _elapsed_ms(t_start: float) -> int:
    return int((time.monotonic() - t_start) * 1000)
