"""
Tests for AgentTestRun RAG fields and AgentTestRunRetrievedChunk model — Phase 4.3.2.

Validates that:
- Migration 026 fields are present and default correctly on AgentTestRun.
- Migration 027 table exists and FK cascade works.
- No changes were made to agent_test_service or other services.
"""

import uuid

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_test_run import AgentTestRun
from app.models.agent_test_run_retrieved_chunk import AgentTestRunRetrievedChunk
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_source import KnowledgeSource
from app.services.embedding_providers.mock import MockEmbeddingProvider
from app.services.indexing_service import index_source
from tests.conftest import _make_ai_model, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup(db: Session):
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    model = _make_ai_model(db)
    agent = Agent(workspace_id=ws.id, name="Agent", status="active")
    db.add(agent)
    db.flush()
    return ws, owner, agent, model


def _make_run(db: Session, ws, owner, agent, model, **kwargs) -> AgentTestRun:
    defaults = dict(
        workspace_id=ws.id,
        agent_id=agent.id,
        user_id=owner.id,
        ai_model_id=model.id,
        provider_code="test",
        model_code="test-model",
        model_name="test-model-v1",
        credits_used=1,
        input_tokens=10,
        output_tokens=20,
        duration_ms=500,
        status="success",
    )
    defaults.update(kwargs)
    run = AgentTestRun(**defaults)
    db.add(run)
    db.flush()
    return run


# ── 1. AgentTestRun RAG field defaults ───────────────────────────────────────

def test_rag_used_defaults_to_false(db: Session):
    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model)
    db.commit()
    db.refresh(run)
    assert run.rag_used is False


def test_retrieval_attempted_defaults_to_false(db: Session):
    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model)
    db.commit()
    db.refresh(run)
    assert run.retrieval_attempted is False


def test_nullable_rag_fields_default_to_none(db: Session):
    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model)
    db.commit()
    db.refresh(run)
    assert run.retrieved_chunks_count is None
    assert run.retrieval_duration_ms is None
    assert run.retrieval_score_max is None
    assert run.retrieval_score_min is None
    assert run.retrieval_error_message is None


def test_rag_fields_can_be_set(db: Session):
    ws, owner, agent, model = _setup(db)
    run = _make_run(
        db, ws, owner, agent, model,
        rag_used=True,
        retrieval_attempted=True,
        retrieved_chunks_count=3,
        retrieval_duration_ms=42,
        retrieval_score_max=0.95,
        retrieval_score_min=0.72,
    )
    db.commit()
    db.refresh(run)
    assert run.rag_used is True
    assert run.retrieval_attempted is True
    assert run.retrieved_chunks_count == 3
    assert run.retrieval_duration_ms == 42
    assert abs(run.retrieval_score_max - 0.95) < 1e-6
    assert abs(run.retrieval_score_min - 0.72) < 1e-6


def test_retrieval_error_message_can_be_set(db: Session):
    ws, owner, agent, model = _setup(db)
    run = _make_run(
        db, ws, owner, agent, model,
        retrieval_attempted=True,
        retrieval_error_message="Provider is down",
    )
    db.commit()
    db.refresh(run)
    assert run.retrieval_error_message == "Provider is down"


# ── 2. AgentTestRunRetrievedChunk basic persistence ──────────────────────────

def test_retrieved_chunk_row_can_be_created(db: Session):
    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model, rag_used=True, retrieval_attempted=True)

    kb_id = uuid.uuid4()
    src_id = uuid.uuid4()
    row = AgentTestRunRetrievedChunk(
        agent_test_run_id=run.id,
        knowledge_chunk_id=None,
        knowledge_base_id=kb_id,
        source_id=src_id,
        score=0.88,
        rank=1,
        injected_into_prompt=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    assert row.id is not None
    assert row.agent_test_run_id == run.id
    assert row.knowledge_chunk_id is None
    assert row.knowledge_base_id == kb_id
    assert abs(row.score - 0.88) < 1e-6
    assert row.rank == 1
    assert row.injected_into_prompt is True
    assert row.created_at is not None


def test_retrieved_chunk_injected_defaults_to_true(db: Session):
    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model)
    row = AgentTestRunRetrievedChunk(
        agent_test_run_id=run.id,
        knowledge_base_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        score=0.5,
        rank=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    assert row.injected_into_prompt is True


def test_filtered_chunk_can_be_recorded(db: Session):
    """A chunk filtered by injection detection is stored with injected_into_prompt=False."""
    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model)
    row = AgentTestRunRetrievedChunk(
        agent_test_run_id=run.id,
        knowledge_base_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        score=0.75,
        rank=2,
        injected_into_prompt=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    assert row.injected_into_prompt is False


# ── 3. FK with real knowledge_chunk_id ───────────────────────────────────────

def test_retrieved_chunk_with_real_chunk_id(db: Session):
    ws, owner, agent, model = _setup(db)

    kb = KnowledgeBase(workspace_id=ws.id, name="KB", status="active")
    db.add(kb)
    db.flush()

    src = KnowledgeSource(
        workspace_id=ws.id,
        knowledge_base_id=kb.id,
        source_type="manual_text",
        title="T",
        content_text="Hello world content for retrieval chunk test.",
        status="processing",
    )
    db.add(src)
    db.flush()
    index_source(db, src, provider=MockEmbeddingProvider(dimension=1536))
    db.flush()

    from sqlalchemy import select

    from app.models.knowledge_chunk import KnowledgeChunk
    chunk = db.scalar(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == src.id)
    )
    assert chunk is not None

    run = _make_run(db, ws, owner, agent, model)
    row = AgentTestRunRetrievedChunk(
        agent_test_run_id=run.id,
        knowledge_chunk_id=chunk.id,
        knowledge_base_id=kb.id,
        source_id=src.id,
        score=0.91,
        rank=1,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    assert row.knowledge_chunk_id == chunk.id


# ── 4. Cascade: deleting AgentTestRun removes retrieved chunk rows ────────────

def test_cascade_delete_run_removes_retrieved_chunks(db: Session):
    from sqlalchemy import select

    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model)
    run_id = run.id

    for rank in range(1, 4):
        db.add(AgentTestRunRetrievedChunk(
            agent_test_run_id=run_id,
            knowledge_base_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            score=0.9 - rank * 0.1,
            rank=rank,
        ))
    db.commit()

    # Verify rows exist
    rows_before = db.scalars(
        select(AgentTestRunRetrievedChunk)
        .where(AgentTestRunRetrievedChunk.agent_test_run_id == run_id)
    ).all()
    assert len(rows_before) == 3

    # Delete the run
    db.delete(run)
    db.commit()

    rows_after = db.scalars(
        select(AgentTestRunRetrievedChunk)
        .where(AgentTestRunRetrievedChunk.agent_test_run_id == run_id)
    ).all()
    assert rows_after == []


# ── 5. Multiple retrieved chunks per run ──────────────────────────────────────

def test_multiple_chunks_per_run(db: Session):
    from sqlalchemy import select

    ws, owner, agent, model = _setup(db)
    run = _make_run(db, ws, owner, agent, model, rag_used=True, retrieved_chunks_count=5)

    for rank in range(1, 6):
        db.add(AgentTestRunRetrievedChunk(
            agent_test_run_id=run.id,
            knowledge_base_id=uuid.uuid4(),
            source_id=uuid.uuid4(),
            score=round(1.0 - rank * 0.05, 2),
            rank=rank,
        ))
    db.commit()

    rows = db.scalars(
        select(AgentTestRunRetrievedChunk)
        .where(AgentTestRunRetrievedChunk.agent_test_run_id == run.id)
        .order_by(AgentTestRunRetrievedChunk.rank)
    ).all()
    assert len(rows) == 5
    assert [r.rank for r in rows] == [1, 2, 3, 4, 5]
