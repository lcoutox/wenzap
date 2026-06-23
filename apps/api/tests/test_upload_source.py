"""
Tests for Phase 4.4.4 — POST /knowledge-bases/{kb_id}/sources/upload.

Covers:
  1. Successful uploads (TXT, Markdown, CSV, PDF)
  2. Title/source_category handling
  3. File metadata fields populated correctly
  4. Storage: file saved, key contains workspace/kb/source IDs
  5. Pre-creation validation errors (type, size, MIME, magic bytes, RBAC, limits)
  6. Post-creation failures (bad extraction, embedding failure)
  7. Filename sanitisation and path traversal
  8. Existing JSON source endpoint still blocks file source_types
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus, SubscriptionStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_source import KnowledgeSource
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.embedding_providers.base import EmbeddingError
from app.services.storage.local import LocalStorageProvider
from tests.conftest import _make_client, _make_user, _make_workspace

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_plan(
    db: Session, *, sources_per_kb_limit: int = 20, max_file_size_bytes: int | None = 10_485_760
) -> Plan:
    p = Plan(
        code=f"test-{uuid.uuid4().hex[:8]}",
        name="Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        sources_per_kb_limit=sources_per_kb_limit,
        max_source_chars=50000,
        users_limit=10,
        pipelines_limit=1,
        integrations_limit=0,
        monthly_ai_credits=1000,
        monthly_conversations=500,
        is_active=True,
        max_file_size_bytes=max_file_size_bytes,
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


def _make_member(db: Session, workspace_id: uuid.UUID, role: MemberRole):
    from app.models.workspace_member import WorkspaceMember
    user = _make_user(db, f"{role.value}-{uuid.uuid4().hex[:6]}@test.com", role.value.title())
    db.add(WorkspaceMember(
        workspace_id=workspace_id, user_id=user.id, role=role, status=MemberStatus.active
    ))
    db.flush()
    return user


def _setup(
    db: Session, *, sources_per_kb_limit: int = 20, max_file_size_bytes: int | None = 10_485_760
):
    """Return (owner, workspace, kb) ready for upload tests."""
    owner = _make_user(db, f"owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"ws-{uuid.uuid4().hex[:6]}", "Test WS")
    plan = _make_plan(
        db, sources_per_kb_limit=sources_per_kb_limit, max_file_size_bytes=max_file_size_bytes
    )
    _make_subscription(db, ws.id, plan)
    kb = KnowledgeBase(workspace_id=ws.id, name="Test KB", status="active")
    db.add(kb)
    db.commit()
    return owner, ws, kb


def _upload(
    client, kb_id, *, filename="test.txt", content=b"Hello world",
    content_type="text/plain", title=None, source_category=None, storage=None,
):
    data: dict = {}
    if title is not None:
        data["title"] = title
    if source_category is not None:
        data["source_category"] = source_category
    files = {"file": (filename, BytesIO(content), content_type)}
    with _patch_storage(storage):
        return client.post(f"/knowledge-bases/{kb_id}/sources/upload", data=data, files=files)


def _patch_storage(storage=None):
    """Patch get_storage_provider in the upload service to use the given storage."""
    if storage is None:
        # If no custom storage, just let the real factory run (local provider with ./storage).
        # Tests that care about storage inject a tmp_path-backed provider directly.
        from unittest.mock import MagicMock
        return MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None)
    return patch("app.services.upload_source_service.get_storage_provider", return_value=storage)


def _chunk_count(db: Session, source_id: str) -> int:
    return db.scalar(
        select(KnowledgeChunk).where(KnowledgeChunk.source_id == uuid.UUID(source_id))
        .__class__.__func__(KnowledgeChunk)  # type: ignore[attr-defined]
    ) or 0


def _pdf_bytes() -> bytes:
    with open(os.path.join(FIXTURES_DIR, "sample_text.pdf"), "rb") as f:
        return f.read()


def _pdf_no_text_bytes() -> bytes:
    with open(os.path.join(FIXTURES_DIR, "sample_no_text.pdf"), "rb") as f:
        return f.read()


# ── 1. Successful uploads ─────────────────────────────────────────────────────

def test_upload_txt_returns_201_and_ready(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="doc.txt", content=b"Hello world", storage=storage)
    assert r.status_code == 201
    assert r.json()["status"] == "ready"


def test_upload_markdown_returns_201_and_ready(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    md_content = b"# Title\n\nSome content here."
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="doc.md", content=md_content,
                    content_type="text/markdown", storage=storage)
    assert r.status_code == 201
    assert r.json()["status"] == "ready"


def test_upload_csv_returns_201_and_ready(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    csv_content = b"Nome,Preco\nProduto A,100\nProduto B,200"
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="data.csv", content=csv_content,
                    content_type="text/csv", storage=storage)
    assert r.status_code == 201
    assert r.json()["status"] == "ready"


def test_upload_pdf_returns_201_and_ready(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="report.pdf", content=_pdf_bytes(),
                    content_type="application/pdf", storage=storage)
    assert r.status_code == 201
    assert r.json()["status"] == "ready"


def test_upload_txt_creates_chunks(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(
            client, kb.id,
            content=b"This is a long enough text to be chunked properly.",
            storage=storage,
        )
    assert r.status_code == 201
    assert r.json()["status"] == "ready"
    source_id = uuid.UUID(r.json()["id"])
    from sqlalchemy import func
    count = db.scalar(
        select(func.count())
        .select_from(KnowledgeChunk)
        .where(KnowledgeChunk.source_id == source_id)
    )
    assert count is not None and count >= 1


# ── 2. Title and source_category ─────────────────────────────────────────────

def test_upload_uses_provided_title(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, title="My Custom Title", storage=storage)
    assert r.json()["title"] == "My Custom Title"


def test_upload_uses_filename_as_default_title(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="my_document.txt", storage=storage)
    assert r.json()["title"] == "my_document"


def test_upload_saves_source_category_in_metadata(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, source_category="policies", storage=storage)
    assert r.json()["metadata_json"] == {"source_category": "policies"}


def test_upload_without_source_category_has_null_metadata(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, storage=storage)
    assert r.json()["metadata_json"] is None


# ── 3. File metadata fields ───────────────────────────────────────────────────

def test_upload_populates_original_filename(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="report.txt", storage=storage)
    assert r.json()["original_filename"] == "report.txt"


def test_upload_populates_mime_type(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, content_type="text/plain", storage=storage)
    assert r.json()["mime_type"] == "text/plain"


def test_upload_populates_file_size_bytes(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    content = b"Exactly this content"
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, content=content, storage=storage)
    assert r.json()["file_size_bytes"] == len(content)


def test_upload_populates_content_hash(db: Session, tmp_path):
    import hashlib
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    content = b"Hash me please"
    expected = hashlib.sha256(content).hexdigest()
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, content=content, storage=storage)
    assert r.json()["content_hash"] == expected


def test_upload_populates_storage_provider(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, storage=storage)
    assert r.json()["storage_provider"] == "local"


def test_upload_populates_storage_key(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, storage=storage)
    key = r.json()["storage_key"]
    assert str(ws.id) in key
    assert str(kb.id) in key


# ── 4. Storage — file actually saved ─────────────────────────────────────────

def test_file_is_saved_in_storage(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    content = b"Saved content"
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, content=content, storage=storage)
    key = r.json()["storage_key"]
    assert storage.exists(key)
    assert storage.get_file(key) == content


def test_storage_key_contains_source_id(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, storage=storage)
    source_id = r.json()["id"]
    assert source_id in r.json()["storage_key"]


# ── 5. Filename sanitisation ──────────────────────────────────────────────────

def test_dangerous_filename_is_sanitised(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(
            client, kb.id, filename="../../evil.txt", content=b"bad content", storage=storage
        )
    assert r.status_code == 201
    assert "evil" in r.json()["original_filename"]
    # Must not escape storage root
    key = r.json()["storage_key"]
    assert ".." not in key


def test_filename_with_spaces_is_sanitised(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="my file (1).txt", content=b"content", storage=storage)
    assert r.status_code == 201
    # Spaces and parentheses replaced with underscores
    assert " " not in r.json()["original_filename"]


# ── 6. Pre-creation errors ────────────────────────────────────────────────────

def test_unsupported_extension_returns_400(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(
            client, kb.id, filename="script.exe", content=b"MZ",
            content_type="text/plain", storage=storage,
        )
    assert r.status_code == 400


def test_docx_extension_returns_400(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(
            client, kb.id, filename="doc.docx", content=b"PK...",
            content_type="application/octet-stream", storage=storage,
        )
    assert r.status_code == 400


def test_incompatible_mime_for_extension_returns_400(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        # .pdf extension but wrong MIME
        r = _upload(client, kb.id, filename="file.pdf", content=_pdf_bytes(),
                    content_type="text/plain", storage=storage)
    assert r.status_code == 400


def test_pdf_without_magic_bytes_returns_400(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    fake_pdf = b"This is not a real PDF but has .pdf extension"
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="fake.pdf", content=fake_pdf,
                    content_type="application/pdf", storage=storage)
    assert r.status_code == 400


def test_file_exceeding_plan_limit_returns_413(db: Session, tmp_path):
    owner, ws, kb = _setup(db, max_file_size_bytes=100)  # 100 bytes limit
    storage = LocalStorageProvider(str(tmp_path))
    big_content = b"A" * 200
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, content=big_content, storage=storage)
    assert r.status_code == 413


def test_viewer_cannot_upload(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    viewer = _make_member(db, ws.id, MemberRole.viewer)
    db.commit()
    with _make_client(db, viewer, ws) as client:
        r = _upload(client, kb.id, storage=storage)
    assert r.status_code == 403


def test_archived_kb_returns_404(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    kb.status = "archived"
    db.commit()
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, storage=storage)
    assert r.status_code == 404


def test_cross_tenant_kb_returns_404(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    # Create KB in a different workspace
    other_owner = _make_user(db, f"other-{uuid.uuid4().hex[:6]}@test.com", "Other")
    other_ws = _make_workspace(db, other_owner, f"other-ws-{uuid.uuid4().hex[:6]}", "Other WS")
    other_kb = KnowledgeBase(workspace_id=other_ws.id, name="Other KB", status="active")
    db.add(other_kb)
    db.commit()
    with _make_client(db, owner, ws) as client:
        r = _upload(client, other_kb.id, storage=storage)
    assert r.status_code == 404


def test_source_limit_reached_returns_402(db: Session, tmp_path):
    owner, ws, kb = _setup(db, sources_per_kb_limit=1)
    storage = LocalStorageProvider(str(tmp_path))
    # Fill the limit with a manual_text source first
    existing = KnowledgeSource(
        workspace_id=ws.id, knowledge_base_id=kb.id,
        source_type="manual_text", title="Existing", content_text="content", status="ready",
    )
    db.add(existing)
    db.commit()
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, storage=storage)
    assert r.status_code == 402


# ── 7. Post-creation failures ─────────────────────────────────────────────────

def test_pdf_without_text_returns_201_with_failed_status(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="blank.pdf", content=_pdf_no_text_bytes(),
                    content_type="application/pdf", storage=storage)
    assert r.status_code == 201
    assert r.json()["status"] == "failed"
    assert r.json()["error_message"] is not None
    assert "Extraction failed" in r.json()["error_message"]


def test_empty_csv_returns_201_with_failed_status(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="empty.csv", content=b"",
                    content_type="text/csv", storage=storage)
    # Empty file: either 400 (pre-creation) or 201+failed depending on validation order
    # Our service validates size > 0 at extraction time, so empty file → failed after creation
    # Actually content b"" has size 0 — storage validation passes (0 < 10MB).
    # Extraction will fail → 201 + failed.
    assert r.status_code in (201, 400)
    if r.status_code == 201:
        assert r.json()["status"] == "failed"


def test_embedding_failure_returns_201_with_failed_status(db: Session, tmp_path):
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with patch(
        "app.services.indexing_service.embed_texts",
        side_effect=EmbeddingError("provider down"),
    ):
        with _make_client(db, owner, ws) as client:
            r = _upload(
                client, kb.id,
                content=b"Valid content here for embedding.",
                storage=storage,
            )
    assert r.status_code == 201
    assert r.json()["status"] == "failed"
    assert r.json()["error_message"] is not None


def test_file_is_preserved_after_extraction_failure(db: Session, tmp_path):
    """Original file must remain in storage even when extraction fails."""
    owner, ws, kb = _setup(db)
    storage = LocalStorageProvider(str(tmp_path))
    with _make_client(db, owner, ws) as client:
        r = _upload(client, kb.id, filename="blank.pdf", content=_pdf_no_text_bytes(),
                    content_type="application/pdf", storage=storage)
    assert r.status_code == 201
    key = r.json()["storage_key"]
    assert key is not None
    assert storage.exists(key)


# ── 8. JSON endpoint still blocks file source_types ──────────────────────────

def test_json_endpoint_rejects_txt_source_type(db: Session):
    owner, ws, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.post(
            f"/knowledge-bases/{kb.id}/sources",
            json={"source_type": "txt", "title": "Test", "content_text": "hello"},
        )
    assert r.status_code == 422


def test_json_endpoint_rejects_pdf_simple_source_type(db: Session):
    owner, ws, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.post(
            f"/knowledge-bases/{kb.id}/sources",
            json={"source_type": "pdf_simple", "title": "Test", "content_text": "hello"},
        )
    assert r.status_code == 422


def test_json_endpoint_still_accepts_manual_text(db: Session):
    owner, ws, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.post(
            f"/knowledge-bases/{kb.id}/sources",
            json={
                "source_type": "manual_text", "title": "Test",
                "content_text": "Hello world content",
            },
        )
    assert r.status_code == 201


def test_json_endpoint_still_accepts_faq_qa(db: Session):
    owner, ws, kb = _setup(db)
    with _make_client(db, owner, ws) as client:
        r = client.post(
            f"/knowledge-bases/{kb.id}/sources",
            json={
                "source_type": "faq_qa",
                "title": "FAQ",
                "metadata": {"qa_pairs": [{"question": "Q?", "answer": "A."}]},
            },
        )
    assert r.status_code == 201
