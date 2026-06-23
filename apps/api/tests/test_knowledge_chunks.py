"""
Tests for GET /knowledge-bases/{kb_id}/sources/{source_id}/chunks — Phase 4.2.4.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus, SubscriptionStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_plan(db: Session) -> Plan:
    p = Plan(
        code=f"plan-{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        sources_per_kb_limit=20,
        max_source_chars=50000,
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
    db.add(WorkspaceSubscription(
        workspace_id=workspace_id,
        plan_id=plan.id,
        status=SubscriptionStatus.active.value,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    ))
    db.flush()


def _make_member(db: Session, workspace_id: uuid.UUID, role: MemberRole):
    from app.models.workspace_member import WorkspaceMember
    user = _make_user(db, f"{role.value}-{uuid.uuid4().hex[:6]}@test.com", role.value.title())
    db.add(WorkspaceMember(
        workspace_id=workspace_id, user_id=user.id, role=role, status=MemberStatus.active,
    ))
    db.flush()
    return user


def _setup(db: Session):
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "WS")
    plan = _make_plan(db)
    _make_subscription(db, ws.id, plan)
    kb = KnowledgeBase(workspace_id=ws.id, name="KB", status="active")
    db.add(kb)
    db.commit()
    return owner, ws, kb.id


def _create_source(client, kb_id, *, content="Hello world content."):
    return client.post(
        f"/knowledge-bases/{kb_id}/sources",
        json={"source_type": "manual_text", "title": "T", "content_text": content},
    ).json()["id"]


def _get_chunks(client, kb_id, source_id):
    return client.get(f"/knowledge-bases/{kb_id}/sources/{source_id}/chunks")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Basic behaviour
# ═══════════════════════════════════════════════════════════════════════════════

def test_list_chunks_returns_200(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id)
        r = _get_chunks(client, kb_id, src_id)
    assert r.status_code == 200


def test_list_chunks_returns_list(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id, content="Some valid content for chunking purposes.")
        r = _get_chunks(client, kb_id, src_id)
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_list_chunks_ordered_by_chunk_index(db):
    owner, ws, kb_id = _setup(db)
    # Generate multiple chunks with long content
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id, content="word " * 1000)
        chunks = _get_chunks(client, kb_id, src_id).json()
    indices = [c["chunk_index"] for c in chunks]
    assert indices == sorted(indices)
    assert len(indices) > 1


def test_list_chunks_does_not_return_embedding(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id)
        chunks = _get_chunks(client, kb_id, src_id).json()
    assert len(chunks) >= 1
    for chunk in chunks:
        assert "embedding" not in chunk


def test_list_chunks_contains_expected_fields(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id)
        chunks = _get_chunks(client, kb_id, src_id).json()
    chunk = chunks[0]
    for field in ("id", "chunk_index", "content", "char_count", "embedding_provider",
                  "embedding_model", "embedding_dimension", "created_at", "updated_at"):
        assert field in chunk, f"Missing field: {field}"


def test_list_chunks_source_with_no_content_returns_empty(db):
    """A source that failed indexing (empty content) should have no chunks."""
    owner, ws, kb_id = _setup(db)
    from unittest.mock import patch

    from app.services.embedding_providers.base import EmbeddingError
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("down"),
    ):
        with _make_client(db, owner, ws) as client:
            src_id = _create_source(client, kb_id)
    with _make_client(db, owner, ws) as client:
        chunks = _get_chunks(client, kb_id, src_id).json()
    assert chunks == []


# ═══════════════════════════════════════════════════════════════════════════════
# 2. RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_viewer_can_list_chunks(db):
    owner, ws, kb_id = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _create_source(c_owner, kb_id)
    with _make_client(db, viewer, ws) as c_viewer:
        r = _get_chunks(c_viewer, kb_id, src_id)
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 404 guards
# ═══════════════════════════════════════════════════════════════════════════════

def test_chunks_archived_source_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id)
        client.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
        r = _get_chunks(client, kb_id, src_id)
    assert r.status_code == 404


def test_chunks_archived_kb_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id)
        client.delete(f"/knowledge-bases/{kb_id}")
        r = _get_chunks(client, kb_id, src_id)
    assert r.status_code == 404


def test_chunks_cross_tenant_returns_404(db):
    owner_a, ws_a, kb_a = _setup(db)
    owner_b, ws_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        src_id = _create_source(c_a, kb_a)
    with _make_client(db, owner_b, ws_b) as c_b:
        r = _get_chunks(c_b, kb_b, src_id)
    assert r.status_code == 404
