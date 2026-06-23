"""
Tests for knowledge_retrieval_service — Phase 4.2.4.

Uses a real PostgreSQL test database.
Chunks are seeded by calling index_source with MockEmbeddingProvider.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_source import KnowledgeSource
from app.services.embedding_providers.mock import MockEmbeddingProvider
from app.services.indexing_service import index_source
from app.services.knowledge_retrieval_service import RetrievedChunk, search_similar_chunks
from tests.conftest import _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

PROVIDER = MockEmbeddingProvider(dimension=1536)


def _setup(db: Session):
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    kb = KnowledgeBase(workspace_id=ws.id, name="KB", status="active")
    db.add(kb)
    db.flush()
    return ws.id, kb.id


def _make_source(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    *,
    content: str = "Hello world content for testing retrieval.",
    source_type: str = "manual_text",
    status: str = "processing",
    metadata_json: dict | None = None,
) -> KnowledgeSource:
    src = KnowledgeSource(
        workspace_id=workspace_id,
        knowledge_base_id=kb_id,
        source_type=source_type,
        title="Test Source",
        content_text=content,
        status=status,
        metadata_json=metadata_json,
    )
    db.add(src)
    db.flush()
    return src


def _seed(db: Session, ws_id, kb_id, content: str) -> KnowledgeSource:
    """Create and index a source so it has real chunks + embeddings."""
    src = _make_source(db, ws_id, kb_id, content=content)
    index_source(db, src, provider=PROVIDER)
    db.flush()
    return src


# ── Guard conditions ──────────────────────────────────────────────────────────

def test_empty_kb_ids_returns_empty(db: Session):
    ws_id, kb_id = _setup(db)
    query_emb = PROVIDER._embed_one("test query")
    result = search_similar_chunks(db, ws_id, [], query_emb, top_k=5)
    assert result == []


def test_top_k_zero_returns_empty(db: Session):
    ws_id, kb_id = _setup(db)
    _seed(db, ws_id, kb_id, "Some content here.")
    query_emb = PROVIDER._embed_one("test query")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=0)
    assert result == []


def test_top_k_negative_returns_empty(db: Session):
    ws_id, kb_id = _setup(db)
    _seed(db, ws_id, kb_id, "Some content here.")
    query_emb = PROVIDER._embed_one("test query")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=-1)
    assert result == []


# ── Basic retrieval ───────────────────────────────────────────────────────────

def test_retrieval_returns_results(db: Session):
    ws_id, kb_id = _setup(db)
    _seed(db, ws_id, kb_id, "Customer support FAQ content for retrieval testing.")
    query_emb = PROVIDER._embed_one("customer support")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=5)
    assert len(result) >= 1
    assert isinstance(result[0], RetrievedChunk)


def test_retrieval_respects_top_k(db: Session):
    ws_id, kb_id = _setup(db)
    # Create content large enough to produce multiple chunks
    _seed(db, ws_id, kb_id, "word " * 1000)
    query_emb = PROVIDER._embed_one("word content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=2)
    assert len(result) <= 2


def test_retrieval_result_has_correct_fields(db: Session):
    ws_id, kb_id = _setup(db)
    _seed(db, ws_id, kb_id, "Test content for field verification.")
    query_emb = PROVIDER._embed_one("test")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=1)
    assert len(result) == 1
    r = result[0]
    assert r.workspace_id == ws_id
    assert r.knowledge_base_id == kb_id
    assert isinstance(r.content, str)
    assert isinstance(r.score, float)
    assert r.rank == 1


def test_retrieval_rank_is_1_based(db: Session):
    ws_id, kb_id = _setup(db)
    _seed(db, ws_id, kb_id, "word " * 1000)
    query_emb = PROVIDER._embed_one("word content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=5)
    assert result[0].rank == 1
    for i, r in enumerate(result, start=1):
        assert r.rank == i


def test_retrieval_scores_are_ordered_desc(db: Session):
    ws_id, kb_id = _setup(db)
    _seed(db, ws_id, kb_id, "word " * 1000)
    query_emb = PROVIDER._embed_one("word content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=5)
    if len(result) > 1:
        scores = [r.score for r in result]
        assert scores == sorted(scores, reverse=True)


# ── Workspace isolation ───────────────────────────────────────────────────────

def test_retrieval_filters_by_workspace(db: Session):
    ws_a, kb_a = _setup(db)
    ws_b, kb_b = _setup(db)
    _seed(db, ws_a, kb_a, "Workspace A exclusive content.")
    _seed(db, ws_b, kb_b, "Workspace B exclusive content.")
    query_emb = PROVIDER._embed_one("content")
    result_a = search_similar_chunks(db, ws_a, [kb_a], query_emb, top_k=10)
    result_b = search_similar_chunks(db, ws_b, [kb_b], query_emb, top_k=10)
    ids_a = {r.workspace_id for r in result_a}
    ids_b = {r.workspace_id for r in result_b}
    assert ids_a == {ws_a}
    assert ids_b == {ws_b}


def test_retrieval_filters_by_kb_ids(db: Session):
    ws_id, kb_id = _setup(db)
    kb2 = KnowledgeBase(workspace_id=ws_id, name="KB2", status="active")
    db.add(kb2)
    db.flush()
    _seed(db, ws_id, kb_id, "KB1 content here.")
    _seed(db, ws_id, kb2.id, "KB2 content here.")
    query_emb = PROVIDER._embed_one("content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=10)
    for r in result:
        assert r.knowledge_base_id == kb_id


# ── Source status filtering ───────────────────────────────────────────────────

def test_retrieval_excludes_failed_source_chunks(db: Session):
    ws_id, kb_id = _setup(db)
    src = _make_source(db, ws_id, kb_id, content="Failed source content.", status="processing")
    index_source(db, src, provider=PROVIDER)
    # Now manually mark the source as failed to simulate a post-indexing failure
    src.status = "failed"
    db.flush()

    query_emb = PROVIDER._embed_one("content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=10)
    src_ids = {r.source_id for r in result}
    assert src.id not in src_ids


def test_retrieval_excludes_archived_source_chunks(db: Session):
    ws_id, kb_id = _setup(db)
    src = _seed(db, ws_id, kb_id, "Archived source content.")
    src.status = "archived"
    db.flush()

    query_emb = PROVIDER._embed_one("content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=10)
    src_ids = {r.source_id for r in result}
    assert src.id not in src_ids


def test_retrieval_excludes_archived_kb(db: Session):
    ws_id, kb_id = _setup(db)
    _seed(db, ws_id, kb_id, "Content in archived KB.")
    # Archive the KB
    kb = db.get(KnowledgeBase, kb_id)
    kb.status = "archived"
    db.flush()

    query_emb = PROVIDER._embed_one("content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=10)
    assert result == []


def test_retrieval_only_searches_ready_sources(db: Session):
    ws_id, kb_id = _setup(db)
    src_ready = _seed(db, ws_id, kb_id, "Ready content for retrieval testing.")
    # Create a pending source (no chunks since it hasn't been indexed)
    _make_source(db, ws_id, kb_id, content="Pending content.", status="pending")
    db.flush()

    query_emb = PROVIDER._embed_one("content")
    result = search_similar_chunks(db, ws_id, [kb_id], query_emb, top_k=10)
    src_ids = {r.source_id for r in result}
    assert src_ready.id in src_ids
