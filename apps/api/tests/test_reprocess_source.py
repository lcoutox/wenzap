"""
Tests for POST /knowledge-bases/{kb_id}/sources/{source_id}/reprocess — Phase 4.2.4.
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
from app.services.embedding_providers.base import EmbeddingError
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


def _create_source(client, kb_id):
    return client.post(
        f"/knowledge-bases/{kb_id}/sources",
        json={
            "source_type": "manual_text",
            "title": "T",
            "content_text": "Hello world content here.",
        },
    )


def _reprocess(client, kb_id, source_id):
    return client.post(f"/knowledge-bases/{kb_id}/sources/{source_id}/reprocess")


def _chunk_count(db: Session, source_id: str) -> int:
    return len(list(db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == uuid.UUID(source_id))
    ).all()))


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Success paths
# ═══════════════════════════════════════════════════════════════════════════════

def test_reprocess_ready_source_returns_200(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        r = _reprocess(client, kb_id, src_id)
    assert r.status_code == 200


def test_reprocess_ready_source_returns_ready(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        r = _reprocess(client, kb_id, src_id)
    assert r.json()["status"] == "ready"


def test_reprocess_failed_source_returns_200(db):
    owner, ws, kb_id = _setup(db)
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("provider down"),
    ):
        with _make_client(db, owner, ws) as client:
            src = _create_source(client, kb_id).json()
            assert src["status"] == "failed"
            src_id = src["id"]

    # Reprocess without the mock patch — should succeed now
    with _make_client(db, owner, ws) as client:
        r = _reprocess(client, kb_id, src_id)
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_reprocess_creates_new_chunks(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        before = _chunk_count(db, src_id)
        _reprocess(client, kb_id, src_id)
        after = _chunk_count(db, src_id)
    assert before >= 1
    assert after >= 1  # chunks still present after reprocess


def test_reprocess_removes_old_chunks_before_creating_new(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        _reprocess(client, kb_id, src_id)
        chunks = list(db.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.source_id == uuid.UUID(src_id))
        ).all())
    # All chunk_indices should be sequential and start at 0 (no duplicates from old run)
    indices = sorted(c.chunk_index for c in chunks)
    assert indices == list(range(len(indices)))


def test_reprocess_processing_source_returns_409(db):
    """If source is already processing, reprocess returns 409."""
    owner, ws, kb_id = _setup(db)
    from app.models.knowledge_source import KnowledgeSource
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
    # Manually set status to processing
    src = db.scalar(select(KnowledgeSource).where(KnowledgeSource.id == uuid.UUID(src_id)))
    src.status = "processing"
    db.commit()
    with _make_client(db, owner, ws) as client:
        r = _reprocess(client, kb_id, src_id)
    assert r.status_code == 409


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Embedding failure during reprocess
# ═══════════════════════════════════════════════════════════════════════════════

def test_reprocess_embedding_failure_returns_200_with_failed(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("provider down"),
    ):
        with _make_client(db, owner, ws) as client:
            r = _reprocess(client, kb_id, src_id)
    assert r.status_code == 200
    assert r.json()["status"] == "failed"


def test_reprocess_embedding_failure_leaves_no_partial_chunks(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("provider down"),
    ):
        with _make_client(db, owner, ws) as client:
            _reprocess(client, kb_id, src_id)
    assert _chunk_count(db, src_id) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 3. RBAC
# ═══════════════════════════════════════════════════════════════════════════════

def test_viewer_cannot_reprocess(db):
    owner, ws, kb_id = _setup(db)
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _create_source(c_owner, kb_id).json()["id"]
    with _make_client(db, viewer, ws) as c_viewer:
        r = _reprocess(c_viewer, kb_id, src_id)
    assert r.status_code == 403


def test_member_can_reprocess(db):
    owner, ws, kb_id = _setup(db)
    member = _make_member(db, ws.id, MemberRole.member)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _create_source(c_owner, kb_id).json()["id"]
    with _make_client(db, member, ws) as c_member:
        r = _reprocess(c_member, kb_id, src_id)
    assert r.status_code == 200


def test_admin_can_reprocess(db):
    owner, ws, kb_id = _setup(db)
    admin = _make_member(db, ws.id, MemberRole.admin)
    db.commit()
    with _make_client(db, owner, ws) as c_owner:
        src_id = _create_source(c_owner, kb_id).json()["id"]
    with _make_client(db, admin, ws) as c_admin:
        r = _reprocess(c_admin, kb_id, src_id)
    assert r.status_code == 200


def test_owner_can_reprocess(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        r = _reprocess(client, kb_id, src_id)
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 404 guards
# ═══════════════════════════════════════════════════════════════════════════════

def test_reprocess_archived_kb_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}")
        r = _reprocess(client, kb_id, src_id)
    assert r.status_code == 404


def test_reprocess_archived_source_returns_404(db):
    owner, ws, kb_id = _setup(db)
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        client.delete(f"/knowledge-bases/{kb_id}/sources/{src_id}")
        r = _reprocess(client, kb_id, src_id)
    assert r.status_code == 404


def test_reprocess_source_in_wrong_kb_returns_404(db):
    owner, ws, kb_id = _setup(db)
    kb2 = KnowledgeBase(workspace_id=ws.id, name="KB2", status="active")
    db.add(kb2)
    db.commit()
    with _make_client(db, owner, ws) as client:
        src_id = _create_source(client, kb_id).json()["id"]
        r = _reprocess(client, kb2.id, src_id)
    assert r.status_code == 404


def test_reprocess_cross_tenant_returns_404(db):
    owner_a, ws_a, kb_a = _setup(db)
    owner_b, ws_b, kb_b = _setup(db)
    with _make_client(db, owner_a, ws_a) as c_a:
        src_id = _create_source(c_a, kb_a).json()["id"]
    with _make_client(db, owner_b, ws_b) as c_b:
        r = _reprocess(c_b, kb_b, src_id)
    assert r.status_code == 404
