"""
Unit/integration tests for indexing_service — Phase 4.2.3.

Uses a real PostgreSQL test database.
MockEmbeddingProvider is always passed explicitly so no external API is called.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_source import KnowledgeSource
from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider, EmbeddingResult
from app.services.embedding_providers.mock import MockEmbeddingProvider
from app.services.indexing_service import IndexingError, delete_source_chunks, index_source
from tests.conftest import _make_user, _make_workspace

# ── Test-only helpers ─────────────────────────────────────────────────────────


class FailingEmbeddingProvider(EmbeddingProvider):
    """Provider that always raises EmbeddingError — used to test failure paths."""

    provider_name = "failing"
    model = "failing-model"
    dimension = 1536

    def embed(self, texts: list[str]) -> EmbeddingResult:
        raise EmbeddingError("Simulated embedding failure")


def _make_source(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    *,
    source_type: str = "manual_text",
    content_text: str | None = "Hello world this is test content",
    metadata_json: dict | None = None,
) -> KnowledgeSource:
    owner_id = db.scalar(select(KnowledgeSource.created_by_user_id).limit(1))
    source = KnowledgeSource(
        workspace_id=workspace_id,
        knowledge_base_id=kb_id,
        source_type=source_type,
        title="Test Source",
        content_text=content_text,
        status="processing",
        metadata_json=metadata_json,
        created_by_user_id=owner_id,
    )
    db.add(source)
    db.flush()
    return source


def _setup(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    """Return (workspace_id, kb_id) with minimal DB records."""
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    kb = KnowledgeBase(workspace_id=ws.id, name="KB", status="active")
    db.add(kb)
    db.flush()
    return ws.id, kb.id


def _count_chunks(db: Session, source_id: uuid.UUID) -> int:
    return db.scalar(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id).with_only_columns(  # type: ignore[arg-type]
            KnowledgeChunk.id
        )
    ) and len(
        list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id)).all())
    ) or len(
        list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id)).all())
    )


# ── index_source — success paths ──────────────────────────────────────────────


def test_index_source_creates_chunks(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id, content_text="Hello world content for testing.")
    provider = MockEmbeddingProvider(dimension=1536)

    chunks = index_source(db, source, provider=provider)

    assert len(chunks) >= 1
    assert source.status == "ready"


def test_index_source_marks_source_ready(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id)
    index_source(db, source, provider=MockEmbeddingProvider())

    assert source.status == "ready"
    assert source.processed_at is not None
    assert source.error_message is None


def test_index_source_populates_embedding_metadata(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id)
    # DB column is vector(1536) — must match exactly.
    provider = MockEmbeddingProvider(dimension=1536)

    chunks = index_source(db, source, provider=provider)

    chunk = chunks[0]
    assert chunk.embedding_provider == "mock"
    assert chunk.embedding_model == "mock-embedding"
    assert chunk.embedding_dimension == 1536


def test_index_source_chunk_embedding_has_correct_dimension(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id)
    provider = MockEmbeddingProvider(dimension=1536)

    chunks = index_source(db, source, provider=provider)

    for chunk in chunks:
        assert len(chunk.embedding) == 1536


def test_index_source_sets_workspace_and_kb_ids(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id)

    chunks = index_source(db, source, provider=MockEmbeddingProvider())

    for chunk in chunks:
        assert chunk.workspace_id == ws_id
        assert chunk.knowledge_base_id == kb_id
        assert chunk.source_id == source.id


def test_index_source_chunk_indices_are_sequential(db: Session):
    ws_id, kb_id = _setup(db)
    # Large enough to produce multiple chunks
    source = _make_source(db, ws_id, kb_id, content_text="word " * 1000)

    chunks = index_source(db, source, provider=MockEmbeddingProvider())

    assert len(chunks) > 1
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_index_source_char_count_matches_content(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id)

    chunks = index_source(db, source, provider=MockEmbeddingProvider())

    for chunk in chunks:
        assert chunk.char_count == len(chunk.content)


def test_index_source_faq_qa_creates_one_chunk_per_pair(db: Session):
    ws_id, kb_id = _setup(db)
    qa_pairs = [
        {"question": "What is X?", "answer": "X is a thing."},
        {"question": "What is Y?", "answer": "Y is another thing."},
        {"question": "What is Z?", "answer": "Z is the last thing."},
    ]
    source = _make_source(
        db, ws_id, kb_id,
        source_type="faq_qa",
        content_text="Pergunta: What is X?\nResposta: X is a thing.\n\n...",
        metadata_json={"qa_pairs": qa_pairs},
    )

    chunks = index_source(db, source, provider=MockEmbeddingProvider())

    assert len(chunks) == 3


def test_index_source_faq_qa_chunk_has_qa_index_metadata(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(
        db, ws_id, kb_id,
        source_type="faq_qa",
        content_text="Pergunta: Q?\nResposta: A.",
        metadata_json={"qa_pairs": [{"question": "Q?", "answer": "A."}]},
    )

    chunks = index_source(db, source, provider=MockEmbeddingProvider())

    assert chunks[0].metadata_json is not None
    assert chunks[0].metadata_json["qa_index"] == 0
    assert chunks[0].metadata_json["source_type"] == "faq_qa"


def test_index_source_faq_qa_short_pair_produces_chunk(db: Session):
    """Regression: 'Pix?' / 'Sim.' must not be filtered out by char length."""
    ws_id, kb_id = _setup(db)
    source = _make_source(
        db, ws_id, kb_id,
        source_type="faq_qa",
        content_text="Pergunta: Pix?\nResposta: Sim.",
        metadata_json={"qa_pairs": [{"question": "Pix?", "answer": "Sim."}]},
    )

    chunks = index_source(db, source, provider=MockEmbeddingProvider())

    assert len(chunks) == 1
    assert "Pix?" in chunks[0].content
    assert "Sim." in chunks[0].content


# ── index_source — removes old chunks before re-indexing ─────────────────────


def test_index_source_removes_old_chunks_before_reindex(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id, content_text="First version content.")

    index_source(db, source, provider=MockEmbeddingProvider())
    db.flush()

    # Simulate reindex with different content
    source.content_text = "Second version content that is completely different from the first."
    index_source(db, source, provider=MockEmbeddingProvider())
    db.flush()

    chunks = list(db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id)
    ).all())

    assert len(chunks) >= 1
    # All chunks now contain second-version content
    for chunk in chunks:
        assert "Second" in chunk.content


# ── delete_source_chunks ──────────────────────────────────────────────────────


def test_delete_source_chunks_removes_only_target_source(db: Session):
    ws_id, kb_id = _setup(db)

    source_a = _make_source(db, ws_id, kb_id, content_text="Source A content here.")
    source_b = _make_source(db, ws_id, kb_id, content_text="Source B content here.")

    index_source(db, source_a, provider=MockEmbeddingProvider())
    index_source(db, source_b, provider=MockEmbeddingProvider())
    db.flush()

    delete_source_chunks(db, source_a.id)
    db.flush()

    chunks_a = list(db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == source_a.id)
    ).all())
    chunks_b = list(db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == source_b.id)
    ).all())

    assert len(chunks_a) == 0
    assert len(chunks_b) >= 1


def test_delete_source_chunks_does_not_cross_workspace(db: Session):
    ws_id_a, kb_id_a = _setup(db)
    ws_id_b, kb_id_b = _setup(db)

    src_a = _make_source(db, ws_id_a, kb_id_a, content_text="Workspace A source content.")
    src_b = _make_source(db, ws_id_b, kb_id_b, content_text="Workspace B source content.")

    index_source(db, src_a, provider=MockEmbeddingProvider())
    index_source(db, src_b, provider=MockEmbeddingProvider())
    db.flush()

    # Delete src_a's chunks — should not affect src_b
    delete_source_chunks(db, src_a.id)
    db.flush()

    chunks_b = list(db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == src_b.id)
    ).all())
    assert len(chunks_b) >= 1


# ── index_source — failure paths ──────────────────────────────────────────────


def test_index_source_fails_if_no_chunks_produced(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id, content_text="   ")  # whitespace only

    with pytest.raises(IndexingError):
        index_source(db, source, provider=MockEmbeddingProvider())

    assert source.status == "failed"
    assert source.error_message is not None


def test_index_source_no_partial_chunks_on_embedding_failure(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id, content_text="Valid content for chunking.")

    with pytest.raises(IndexingError):
        index_source(db, source, provider=FailingEmbeddingProvider())

    db.flush()
    chunks = list(db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id)
    ).all())

    assert len(chunks) == 0
    assert source.status == "failed"
    assert "Embedding failed" in (source.error_message or "")


def test_index_source_embedding_failure_sets_error_message(db: Session):
    ws_id, kb_id = _setup(db)
    source = _make_source(db, ws_id, kb_id)

    with pytest.raises(IndexingError):
        index_source(db, source, provider=FailingEmbeddingProvider())

    assert source.error_message is not None
    assert len(source.error_message) <= 500
