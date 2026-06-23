"""
Tests for retrieve_context_for_agent — Phase 4.3.1.

All tests use real PostgreSQL (test DB) and MockEmbeddingProvider.
No OpenAI or Anthropic calls are made.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_knowledge_base import AgentKnowledgeBase
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_source import KnowledgeSource
from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider, EmbeddingResult
from app.services.embedding_providers.mock import MockEmbeddingProvider
from app.services.indexing_service import index_source
from app.services.knowledge_retrieval_service import RetrievalResult, retrieve_context_for_agent
from tests.conftest import _make_user, _make_workspace

# ── Shared provider ───────────────────────────────────────────────────────────

PROVIDER = MockEmbeddingProvider(dimension=1536)


# ── Fixtures / factories ──────────────────────────────────────────────────────

def _setup(db: Session):
    """Create workspace + agent; return (workspace_id, agent_id)."""
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    agent = Agent(
        workspace_id=ws.id,
        name="Test Agent",
        status="active",
    )
    db.add(agent)
    db.flush()
    return ws.id, agent.id


def _make_kb(db: Session, workspace_id: uuid.UUID, *, status: str = "active") -> KnowledgeBase:
    kb = KnowledgeBase(workspace_id=workspace_id, name=f"KB-{uuid.uuid4().hex[:4]}", status=status)
    db.add(kb)
    db.flush()
    return kb


def _connect_kb(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    kb_id: uuid.UUID,
    *,
    is_active: bool = True,
) -> AgentKnowledgeBase:
    conn = AgentKnowledgeBase(
        workspace_id=workspace_id,
        agent_id=agent_id,
        knowledge_base_id=kb_id,
        is_active=is_active,
    )
    db.add(conn)
    db.flush()
    return conn


def _make_ready_source(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    content: str = "This is test content for retrieval.",
) -> KnowledgeSource:
    """Create a KnowledgeSource and index it so it has real chunks."""
    src = KnowledgeSource(
        workspace_id=workspace_id,
        knowledge_base_id=kb_id,
        source_type="manual_text",
        title="Test Source",
        content_text=content,
        status="processing",
    )
    db.add(src)
    db.flush()
    index_source(db, src, provider=PROVIDER)
    db.flush()
    return src


# ── 1. No KB connected ────────────────────────────────────────────────────────

def test_no_kb_connected_returns_not_attempted(db: Session):
    ws_id, agent_id = _setup(db)
    result = retrieve_context_for_agent(db, ws_id, agent_id, "hello", provider=PROVIDER)
    assert isinstance(result, RetrievalResult)
    assert result.retrieval_attempted is False
    assert result.rag_used is False
    assert result.chunks == []
    assert result.knowledge_base_ids == []
    assert result.error_message is None


def test_no_kb_connected_duration_is_set(db: Session):
    ws_id, agent_id = _setup(db)
    result = retrieve_context_for_agent(db, ws_id, agent_id, "hello", provider=PROVIDER)
    assert isinstance(result.retrieval_duration_ms, int)
    assert result.retrieval_duration_ms >= 0


# ── 2. Connection is_active=False ─────────────────────────────────────────────

def test_inactive_connection_not_attempted(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id, is_active=False)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "test", provider=PROVIDER)
    assert result.retrieval_attempted is False
    assert result.chunks == []


# ── 3. KB status not "active" ─────────────────────────────────────────────────

def test_archived_kb_not_used(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id, status="archived")
    _connect_kb(db, ws_id, agent_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "test", provider=PROVIDER)
    assert result.retrieval_attempted is False
    assert result.chunks == []
    assert kb.id not in result.knowledge_base_ids


def test_inactive_kb_status_not_used(db: Session):
    """Only status='active' KBs are used — 'inactive' is excluded."""
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id, status="inactive")
    _connect_kb(db, ws_id, agent_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "test", provider=PROVIDER)
    assert result.retrieval_attempted is False
    assert result.chunks == []


# ── 4. Active KB with ready chunks ───────────────────────────────────────────

def test_retrieves_chunks_from_active_kb(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id, "Customer support documentation for testing.")
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "customer support", provider=PROVIDER)
    assert result.retrieval_attempted is True
    assert result.rag_used is True
    assert len(result.chunks) >= 1
    assert kb.id in result.knowledge_base_ids
    assert result.error_message is None


def test_kb_id_present_in_result(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "test", provider=PROVIDER)
    assert kb.id in result.knowledge_base_ids


def test_retrieved_chunks_have_correct_workspace(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "test", provider=PROVIDER)
    for chunk in result.chunks:
        assert chunk.workspace_id == ws_id


# ── 5. Source status filtering ────────────────────────────────────────────────

def test_failed_source_chunks_not_returned(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    src = _make_ready_source(db, ws_id, kb.id, "Some content here.")
    src.status = "failed"
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "content", provider=PROVIDER)
    # retrieval_attempted=True (KB is active), but no chunks from failed source
    assert result.retrieval_attempted is True
    assert result.rag_used is False
    assert result.chunks == []


def test_archived_source_chunks_not_returned(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    src = _make_ready_source(db, ws_id, kb.id, "Some content here.")
    src.status = "archived"
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "content", provider=PROVIDER)
    assert result.retrieval_attempted is True
    assert result.rag_used is False
    assert result.chunks == []


# ── 6. Tenant isolation ───────────────────────────────────────────────────────

def test_chunks_from_other_workspace_not_returned(db: Session):
    ws_a, agent_a = _setup(db)
    ws_b, agent_b = _setup(db)

    kb_a = _make_kb(db, ws_a)
    kb_b = _make_kb(db, ws_b)
    _connect_kb(db, ws_a, agent_a, kb_a.id)
    _connect_kb(db, ws_b, agent_b, kb_b.id)

    _make_ready_source(db, ws_a, kb_a.id, "Workspace A secret content.")
    _make_ready_source(db, ws_b, kb_b.id, "Workspace B secret content.")
    db.flush()

    result_a = retrieve_context_for_agent(db, ws_a, agent_a, "secret content", provider=PROVIDER)
    result_b = retrieve_context_for_agent(db, ws_b, agent_b, "secret content", provider=PROVIDER)

    ws_ids_a = {c.workspace_id for c in result_a.chunks}
    ws_ids_b = {c.workspace_id for c in result_b.chunks}

    assert ws_ids_a == {ws_a}
    assert ws_ids_b == {ws_b}


def test_agent_cannot_use_kb_from_other_workspace(db: Session):
    """Agent in ws_a with a KB that belongs to ws_b — connection has ws_a scope."""
    ws_a, agent_a = _setup(db)
    ws_b, agent_b = _setup(db)

    # KB belongs to ws_b; agent belongs to ws_a; no connection exists
    kb_b = _make_kb(db, ws_b)
    _make_ready_source(db, ws_b, kb_b.id, "Cross-tenant content.")
    db.flush()

    # No connection in ws_a → no retrieval
    result = retrieve_context_for_agent(db, ws_a, agent_a, "content", provider=PROVIDER)
    assert result.retrieval_attempted is False
    assert result.chunks == []


# ── 7. Query guards ───────────────────────────────────────────────────────────

def test_empty_query_returns_not_attempted(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "", provider=PROVIDER)
    assert result.retrieval_attempted is False
    assert result.chunks == []


def test_whitespace_query_returns_not_attempted(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "   \t\n  ", provider=PROVIDER)
    assert result.retrieval_attempted is False
    assert result.chunks == []


# ── 8. top_k behaviour ────────────────────────────────────────────────────────

def test_top_k_zero_returns_empty(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id, "word " * 500)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "word", top_k=0, provider=PROVIDER)
    assert result.retrieval_attempted is True  # KB exists, but top_k=0 short-circuits
    assert result.chunks == []
    assert result.rag_used is False


def test_top_k_negative_returns_empty(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id, "word " * 500)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "word", top_k=-1, provider=PROVIDER)
    assert result.retrieval_attempted is True
    assert result.chunks == []
    assert result.rag_used is False


def test_top_k_limits_results(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id, "word " * 1000)  # produces multiple chunks
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "word", top_k=2, provider=PROVIDER)
    assert len(result.chunks) <= 2


def test_top_k_none_uses_settings_default(db: Session):
    """When top_k=None, the setting rag_top_k (default 5) is used — result ≤ 5."""
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    # Produce many chunks by using a very long text
    _make_ready_source(db, ws_id, kb.id, "word " * 5000)
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "word", top_k=None, provider=PROVIDER)
    assert len(result.chunks) <= 5


# ── 9. Embedding / retrieval failure ─────────────────────────────────────────

class _FailingProvider(EmbeddingProvider):
    """Always raises EmbeddingError."""
    provider_name = "failing"
    model = "failing"
    dimension = 1536

    def embed(self, texts: list[str]) -> EmbeddingResult:
        raise EmbeddingError("Provider is down")


def test_embedding_failure_does_not_raise(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    # Must not raise
    result = retrieve_context_for_agent(
        db, ws_id, agent_id, "test", provider=_FailingProvider()
    )
    assert result.retrieval_attempted is True
    assert result.rag_used is False
    assert result.chunks == []
    assert result.error_message is not None
    assert "Provider is down" in result.error_message


def test_embedding_failure_sets_kb_ids(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(
        db, ws_id, agent_id, "test", provider=_FailingProvider()
    )
    assert kb.id in result.knowledge_base_ids


class _CrashingProvider(EmbeddingProvider):
    """Raises an unexpected non-EmbeddingError exception."""
    provider_name = "crashing"
    model = "crashing"
    dimension = 1536

    def embed(self, texts: list[str]) -> EmbeddingResult:
        raise RuntimeError("Unexpected internal crash")


def test_unexpected_exception_does_not_raise(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    result = retrieve_context_for_agent(
        db, ws_id, agent_id, "test", provider=_CrashingProvider()
    )
    assert result.retrieval_attempted is True
    assert result.rag_used is False
    assert result.chunks == []
    assert result.error_message is not None
    assert "Retrieval error" in result.error_message


def test_error_message_truncated_to_500_chars(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id)
    db.flush()

    class _LongErrorProvider(EmbeddingProvider):
        provider_name = "long-error"
        model = "long-error"
        dimension = 1536

        def embed(self, texts: list[str]) -> EmbeddingResult:
            raise EmbeddingError("x" * 600)

    result = retrieve_context_for_agent(
        db, ws_id, agent_id, "test", provider=_LongErrorProvider()
    )
    assert result.error_message is not None
    assert len(result.error_message) <= 500


# ── 10. Multiple KBs ─────────────────────────────────────────────────────────

def test_multiple_active_kbs_all_searched(db: Session):
    ws_id, agent_id = _setup(db)
    kb1 = _make_kb(db, ws_id)
    kb2 = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb1.id)
    _connect_kb(db, ws_id, agent_id, kb2.id)
    _make_ready_source(db, ws_id, kb1.id, "KB1 content about support.")
    _make_ready_source(db, ws_id, kb2.id, "KB2 content about billing.")
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "content", provider=PROVIDER)
    assert result.retrieval_attempted is True
    assert kb1.id in result.knowledge_base_ids
    assert kb2.id in result.knowledge_base_ids
    kb_ids_in_chunks = {c.knowledge_base_id for c in result.chunks}
    # At least one KB contributed chunks
    assert len(kb_ids_in_chunks) >= 1


def test_one_active_one_inactive_connection(db: Session):
    """Only the is_active=True connection is searched."""
    ws_id, agent_id = _setup(db)
    kb1 = _make_kb(db, ws_id)
    kb2 = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb1.id, is_active=True)
    _connect_kb(db, ws_id, agent_id, kb2.id, is_active=False)
    _make_ready_source(db, ws_id, kb1.id, "Active KB content.")
    _make_ready_source(db, ws_id, kb2.id, "Inactive KB content.")
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "content", provider=PROVIDER)
    assert result.retrieval_attempted is True
    assert kb1.id in result.knowledge_base_ids
    assert kb2.id not in result.knowledge_base_ids


# ── 11. Result structure ──────────────────────────────────────────────────────

def test_result_duration_always_non_negative(db: Session):
    ws_id, agent_id = _setup(db)
    result = retrieve_context_for_agent(db, ws_id, agent_id, "hello", provider=PROVIDER)
    assert result.retrieval_duration_ms >= 0


def test_rag_used_false_when_no_chunks_found(db: Session):
    """KB connected + source ready, but no chunks match (empty KB)."""
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    # No source → no chunks
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "test", provider=PROVIDER)
    assert result.retrieval_attempted is True
    assert result.rag_used is False
    assert result.chunks == []


def test_chunk_fields_are_populated(db: Session):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id, "Detailed content for field verification.")
    db.flush()

    result = retrieve_context_for_agent(db, ws_id, agent_id, "content", provider=PROVIDER)
    assert len(result.chunks) >= 1
    chunk = result.chunks[0]
    assert isinstance(chunk.chunk_id, uuid.UUID)
    assert isinstance(chunk.content, str) and chunk.content
    assert isinstance(chunk.score, float)
    assert chunk.rank == 1


@pytest.mark.parametrize("query", [
    "support",
    "What is the refund policy?",
    "Como funciona o sistema?",
])
def test_various_queries_do_not_raise(db: Session, query: str):
    ws_id, agent_id = _setup(db)
    kb = _make_kb(db, ws_id)
    _connect_kb(db, ws_id, agent_id, kb.id)
    _make_ready_source(db, ws_id, kb.id, "General purpose content for testing queries.")
    db.flush()

    # Must not raise for any query string
    result = retrieve_context_for_agent(db, ws_id, agent_id, query, provider=PROVIDER)
    assert isinstance(result, RetrievalResult)
