"""
Tests for Knowledge Source CRUD — Phase 4.1.3.

Covers:
  1. CRUD (create, list, get, archive)
  2. faq_qa content generation and metadata preservation
  3. Plan limits (max_source_chars, sources_per_kb_limit)
  4. RBAC
  5. Tenant isolation
  6. KB archived → 404 on source endpoints
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus, SubscriptionStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider, EmbeddingResult
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_plan(
    db: Session,
    *,
    knowledge_bases_limit: int = 10,
    sources_per_kb_limit: int = 20,
    max_source_chars: int = 50000,
) -> Plan:
    p = Plan(
        code=f"test-plan-{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=knowledge_bases_limit,
        sources_per_kb_limit=sources_per_kb_limit,
        max_source_chars=max_source_chars,
        users_limit=10,
        pipelines_limit=1,
        integrations_limit=0,
        monthly_ai_credits=1000,
        monthly_conversations=500,
        is_active=True,
    )
    db.add(p)
    db.flush()
    return p


def _make_subscription(db: Session, workspace_id: uuid.UUID, plan: Plan) -> None:
    now = datetime.now(timezone.utc)
    sub = WorkspaceSubscription(
        workspace_id=workspace_id,
        plan_id=plan.id,
        status=SubscriptionStatus.active.value,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(sub)
    db.flush()


def _make_member(db: Session, workspace_id: uuid.UUID, role: MemberRole) -> object:
    from app.models.workspace_member import WorkspaceMember

    user = _make_user(
        db,
        f"{role.value}-{uuid.uuid4().hex[:6]}@test.com",
        f"{role.value.title()} User",
    )
    db.add(WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user.id,
        role=role,
        status=MemberStatus.active,
    ))
    db.flush()
    return user


def _setup(
    db: Session,
    *,
    sources_per_kb_limit: int = 20,
    max_source_chars: int = 50000,
):
    """Return (owner, workspace, kb_id) ready for source tests."""
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "Test WS")
    plan = _make_plan(
        db,
        sources_per_kb_limit=sources_per_kb_limit,
        max_source_chars=max_source_chars,
    )
    _make_subscription(db, ws.id, plan)
    kb = KnowledgeBase(workspace_id=ws.id, name="Test KB", status="active")
    db.add(kb)
    db.commit()
    return owner, ws, kb.id


def _post_source(client, kb_id, **kwargs) -> object:
    body: dict = {
        "source_type": kwargs.get("source_type", "manual_text"),
        "title": kwargs.get("title", "Test Source"),
    }
    if "content_text" in kwargs:
        body["content_text"] = kwargs["content_text"]
    if "metadata" in kwargs:
        body["metadata"] = kwargs["metadata"]
    return client.post(f"/knowledge-bases/{kb_id}/sources", json=body)


def _post_manual(client, kb_id, *, title="Manual Source", content="Hello world"):
    return _post_source(client, kb_id, source_type="manual_text", title=title, content_text=content)


def _post_faq(client, kb_id, *, title="FAQ Source", qa_pairs=None):
    pairs = qa_pairs or [{"question": "Q1", "answer": "A1"}]
    return _post_source(
        client, kb_id,
        source_type="faq_qa",
        title=title,
        metadata={"qa_pairs": pairs},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CRUD — manual_text
# ═══════════════════════════════════════════════════════════════════════════════

def test_create_manual_text_returns_201(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id)
    assert r.status_code == 201


def test_create_manual_text_status_is_ready(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id)
    assert r.json()["status"] == "ready"


def test_create_manual_text_processed_at_is_set(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id)
    assert r.json()["processed_at"] is not None


def test_create_manual_text_fields(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id, title="My Doc", content="Some content here")
    body = r.json()
    assert body["title"] == "My Doc"
    assert body["content_text"] == "Some content here"
    assert body["source_type"] == "manual_text"
    assert body["workspace_id"] == str(ws.id)
    assert body["knowledge_base_id"] == str(kb_id)


def test_create_manual_text_sets_created_by_user_id(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id)
    assert r.json()["created_by_user_id"] == str(owner.id)


def test_list_sources_returns_sources_of_kb(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        _post_manual(client, kb_id, title="Src 1")
        _post_manual(client, kb_id, title="Src 2")
        r = client.get(f"/knowledge-bases/{kb_id}/sources")
    assert r.status_code == 200
    titles = [s["title"] for s in r.json()]
    assert "Src 1" in titles
    assert "Src 2" in titles


def test_get_source_returns_200(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _post_manual(client, kb_id).json()["id"]
        r = client.get(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 200
    assert r.json()["id"] == src_id


def test_archive_source_changes_status(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _post_manual(client, kb_id).json()["id"]
        r = client.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


def test_archived_source_not_in_listing(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _post_manual(client, kb_id).json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
        r = client.get(f"/knowledge-bases/{kb_id}/sources")
    ids = [s["id"] for s in r.json()]
    assert src_id not in ids


def test_get_archived_source_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _post_manual(client, kb_id).json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
        r = client.get(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 404


def test_create_manual_text_empty_title_returns_422(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id, title="")
    assert r.status_code == 422


def test_create_manual_text_empty_content_returns_422(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_source(client, kb_id, source_type="manual_text", title="T", content_text="")
    assert r.status_code == 422


def test_create_manual_text_whitespace_content_returns_422(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_source(client, kb_id, source_type="manual_text", title="T", content_text="   ")
    assert r.status_code == 422


def test_create_manual_text_without_content_returns_422(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_source(client, kb_id, source_type="manual_text", title="T")
    assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# 2. faq_qa — content generation and metadata
# ═══════════════════════════════════════════════════════════════════════════════

def test_create_faq_qa_returns_201(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(client, kb_id)
    assert r.status_code == 201


def test_create_faq_qa_status_is_ready(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(client, kb_id)
    assert r.json()["status"] == "ready"


def test_create_faq_qa_generates_content_text(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(
            client, kb_id,
            qa_pairs=[{"question": "What is X?", "answer": "X is Y."}],
        )
    content = r.json()["content_text"]
    assert "Pergunta: What is X?" in content
    assert "Resposta: X is Y." in content


def test_create_faq_qa_multiple_pairs_separated(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(
            client, kb_id,
            qa_pairs=[
                {"question": "Q1", "answer": "A1"},
                {"question": "Q2", "answer": "A2"},
            ],
        )
    content = r.json()["content_text"]
    assert "Pergunta: Q1" in content
    assert "Pergunta: Q2" in content
    # pairs are separated by double newline
    assert "\n\n" in content


def test_create_faq_qa_preserves_pairs_in_metadata(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(
            client, kb_id,
            qa_pairs=[{"question": "How?", "answer": "Like this."}],
        )
    meta = r.json()["metadata_json"]
    assert meta is not None
    assert "qa_pairs" in meta
    assert meta["qa_pairs"][0]["question"] == "How?"
    assert meta["qa_pairs"][0]["answer"] == "Like this."


def test_create_faq_qa_with_source_category(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_source(
            client, kb_id,
            source_type="faq_qa",
            title="T",
            metadata={
                "source_category": "faq",
                "qa_pairs": [{"question": "Q", "answer": "A"}],
            },
        )
    meta = r.json()["metadata_json"]
    assert meta["source_category"] == "faq"
    assert "qa_pairs" in meta


def test_create_faq_qa_no_pairs_returns_422(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_source(
            client, kb_id,
            source_type="faq_qa",
            title="T",
            metadata={"qa_pairs": []},
        )
    assert r.status_code == 422


def test_create_faq_qa_empty_question_returns_422(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(client, kb_id, qa_pairs=[{"question": "", "answer": "A"}])
    assert r.status_code == 422


def test_create_faq_qa_empty_answer_returns_422(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(client, kb_id, qa_pairs=[{"question": "Q", "answer": ""}])
    assert r.status_code == 422


def test_create_manual_text_with_source_category(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_source(
            client, kb_id,
            source_type="manual_text",
            title="Policy",
            content_text="Our policy is ...",
            metadata={"source_category": "internal_policy"},
        )
    assert r.status_code == 201
    assert r.json()["metadata_json"]["source_category"] == "internal_policy"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Plan limits
# ═══════════════════════════════════════════════════════════════════════════════

def test_content_exceeding_max_chars_returns_400(db):
    owner, ws, kb_id = _setup(db, max_source_chars=10)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id, content="A" * 11)
    assert r.status_code == 400


def test_content_at_max_chars_is_accepted(db):
    owner, ws, kb_id = _setup(db, max_source_chars=10)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id, content="A" * 10)
    assert r.status_code == 201


def test_source_limit_blocks_creation(db):
    owner, ws, kb_id = _setup(db, sources_per_kb_limit=2)
    with _make_client(db, owner, ws) as client:
        _post_manual(client, kb_id, title="S1")
        _post_manual(client, kb_id, title="S2")
        r = _post_manual(client, kb_id, title="S3")
    assert r.status_code == 402


def test_archived_sources_do_not_count_toward_limit(db):
    owner, ws, kb_id = _setup(db, sources_per_kb_limit=2)
    with _make_client(db, owner, ws) as client:
        _post_manual(client, kb_id, title="S1")
        src_id = _post_manual(client, kb_id, title="S2").json()["id"]
        # archive one to free up a slot
        client.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
        r = _post_manual(client, kb_id, title="S3")
    assert r.status_code == 201


# ═══════════════════════════════════════════════════════════════════════════════
# 4. RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_viewer_can_list_sources(db):
    owner, ws, kb_id = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        _post_manual(c_owner, kb_id)
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.get(f"/knowledge-bases/{kb_id}/sources")
    assert r.status_code == 200


def test_viewer_can_get_source(db):
    owner, ws, kb_id = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _post_manual(c_owner, kb_id).json()["id"]
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.get(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 200


def test_viewer_cannot_create_source(db):
    owner, ws, kb_id = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, viewer, ws) as c_viewer:
        r = _post_manual(c_viewer, kb_id)
    assert r.status_code == 403


def test_viewer_cannot_archive_source(db):
    owner, ws, kb_id = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _post_manual(c_owner, kb_id).json()["id"]
    with _make_client(db, viewer, ws) as c_viewer:
        r = c_viewer.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 403


def test_member_can_create_source(db):
    owner, ws, kb_id = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    db.commit()
    with _make_client(db, member, ws) as c_member:
        r = _post_manual(c_member, kb_id)
    assert r.status_code == 201


def test_member_cannot_archive_source(db):
    owner, ws, kb_id = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _post_manual(c_owner, kb_id).json()["id"]
    with _make_client(db, member, ws) as c_member:
        r = c_member.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 403


def test_admin_can_archive_source(db):
    owner, ws, kb_id = _setup(db)
    admin = _make_member(db, ws.id, MemberRole.admin)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _post_manual(c_owner, kb_id).json()["id"]
    with _make_client(db, admin, ws) as c_admin:
        r = c_admin.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 200


def test_owner_can_archive_source(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _post_manual(client, kb_id).json()["id"]
        r = client.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Tenant isolation
# ═══════════════════════════════════════════════════════════════════════════════

def test_list_sources_does_not_leak_cross_workspace(db):
    owner_a, ws_a, kb_a = _setup(db)
    owner_b, ws_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        src_id = _post_manual(c_a, kb_a).json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.get(f"/knowledge-bases/{kb_b}/sources")
    ids = [s["id"] for s in r.json()]
    assert src_id not in ids


def test_get_source_cross_workspace_returns_404(db):
    owner_a, ws_a, kb_a = _setup(db)
    owner_b, ws_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        src_id = _post_manual(c_a, kb_a).json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.get(f"/knowledge-bases/{kb_b}/sources/{src_id}")
    assert r.status_code == 404


def test_post_source_in_cross_workspace_kb_returns_404(db):
    owner_a, ws_a, kb_a = _setup(db)
    owner_b, ws_b, _ = _setup(db)
    with _make_client(db, owner_b, ws_b) as c_b:
        r = _post_manual(c_b, kb_a)
    assert r.status_code == 404


def test_delete_source_cross_workspace_returns_404(db):
    owner_a, ws_a, kb_a = _setup(db)
    owner_b, ws_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        src_id = _post_manual(c_a, kb_a).json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = c_b.delete(f"/knowledge-bases/{kb_b}/sources/{src_id}")
    assert r.status_code == 404


def test_source_from_different_kb_same_workspace_returns_404(db):
    """A source from KB-A cannot be accessed via KB-B even in the same workspace."""
    owner, ws, kb_a = _setup(db)
    kb_b = KnowledgeBase(workspace_id=ws.id, name="KB B", status="active")
    db.add(kb_b)
    db.commit()
    with _make_client(db, owner, ws) as client:
        src_id = _post_manual(client, kb_a).json()["id"]
        r = client.get(f"/knowledge-bases/{kb_b.id}/sources/{src_id}")
    assert r.status_code == 404


def test_nonexistent_source_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.get(f"/knowledge-bases/{kb_id}/sources/{uuid.uuid4()}")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 6. KB archived → source endpoints return 404
# ═══════════════════════════════════════════════════════════════════════════════

def test_list_sources_on_archived_kb_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        client.delete(f"/knowledge-bases/{kb_id}")
        r = client.get(f"/knowledge-bases/{kb_id}/sources")
    assert r.status_code == 404


def test_create_source_on_archived_kb_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        client.delete(f"/knowledge-bases/{kb_id}")
        r = _post_manual(client, kb_id)
    assert r.status_code == 404


def test_get_source_on_archived_kb_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _post_manual(client, kb_id).json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}")
        r = client.get(f"/knowledge-bases/{kb_id}/sources/{src_id}")
    assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Indexing pipeline — chunks created on source creation
# ═══════════════════════════════════════════════════════════════════════════════

def _chunk_count(db: Session, source_id: str) -> int:
    return len(list(db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == uuid.UUID(source_id))
    ).all()))


def test_create_manual_text_creates_chunks(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id, content="Hello world this is some test content.")
    assert r.status_code == 201
    assert _chunk_count(db, r.json()["id"]) >= 1


def test_create_manual_text_large_content_creates_multiple_chunks(db):
    owner, ws, kb_id = _setup(db, max_source_chars=50000)
    # 6 000 chars → more than one 3 000-char chunk
    content = "word " * 1200
    with _make_client(db, owner, ws) as client:
        r = _post_manual(client, kb_id, content=content)
    assert r.status_code == 201
    assert _chunk_count(db, r.json()["id"]) > 1


def test_create_faq_qa_creates_one_chunk_per_pair(db):
    owner, ws, kb_id = _setup(db)
    pairs = [
        {"question": "Q1?", "answer": "A1."},
        {"question": "Q2?", "answer": "A2."},
        {"question": "Q3?", "answer": "A3."},
    ]
    with _make_client(db, owner, ws) as client:
        r = _post_faq(client, kb_id, qa_pairs=pairs)
    assert r.status_code == 201
    assert _chunk_count(db, r.json()["id"]) == 3


def test_create_faq_qa_short_pair_generates_chunk(db):
    """Regression: a valid but short FAQ pair like 'Pix?'/'Sim.' must produce a chunk."""
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = _post_faq(
            client, kb_id,
            qa_pairs=[{"question": "Pix?", "answer": "Sim."}],
        )
    assert r.status_code == 201
    assert r.json()["status"] == "ready"
    assert _chunk_count(db, r.json()["id"]) == 1


def test_create_faq_qa_preserves_qa_pairs_in_metadata(db):
    owner, ws, kb_id = _setup(db)
    pairs = [{"question": "How?", "answer": "Like this."}]
    with _make_client(db, owner, ws) as client:
        r = _post_faq(client, kb_id, qa_pairs=pairs)
    meta = r.json()["metadata_json"]
    assert meta["qa_pairs"][0]["question"] == "How?"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Indexing pipeline — embedding failure returns 201 with status=failed
# ═══════════════════════════════════════════════════════════════════════════════


class _FailingEmbeddingProvider(EmbeddingProvider):
    provider_name = "failing"
    model = "failing-model"
    dimension = 1536

    def embed(self, texts: list[str]) -> EmbeddingResult:
        raise EmbeddingError("Simulated provider failure")


def test_embedding_failure_returns_201_with_failed_status(db):
    owner, ws, kb_id = _setup(db)
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("provider down"),
    ):
        with _make_client(db, owner, ws) as client:
            r = _post_manual(client, kb_id, content="Some valid content here.")
    assert r.status_code == 201
    assert r.json()["status"] == "failed"
    assert r.json()["error_message"] is not None


def test_embedding_failure_leaves_no_partial_chunks(db):
    owner, ws, kb_id = _setup(db)
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("provider down"),
    ):
        with _make_client(db, owner, ws) as client:
            r = _post_manual(client, kb_id, content="Some valid content here.")
    assert _chunk_count(db, r.json()["id"]) == 0


def test_embedding_failure_error_message_is_set(db):
    owner, ws, kb_id = _setup(db)
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("provider down"),
    ):
        with _make_client(db, owner, ws) as client:
            r = _post_manual(client, kb_id, content="Some valid content here.")
    assert "Embedding failed" in r.json()["error_message"]
