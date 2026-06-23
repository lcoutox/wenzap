"""
Tests for Phase 4.4.3 — file fields on knowledge_sources and max_file_size_bytes on plans.

Verifies that:
- KnowledgeSource model accepts file upload fields
- KnowledgeSourceOut serializes file fields correctly
- Existing manual_text sources keep all file fields as None
- Plan model has max_file_size_bytes
- Migration 029 set correct limits per plan code
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_source import KnowledgeSource
from app.models.plan import Plan
from app.models.workspace import Workspace
from app.schemas.knowledge_source import KnowledgeSourceOut

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_kb(db: Session, workspace: Workspace) -> KnowledgeBase:
    kb = KnowledgeBase(workspace_id=workspace.id, name="Test KB", status="active")
    db.add(kb)
    db.flush()
    return kb


def _make_source(db: Session, workspace: Workspace, kb: KnowledgeBase, **kwargs) -> KnowledgeSource:
    source = KnowledgeSource(
        workspace_id=workspace.id,
        knowledge_base_id=kb.id,
        source_type=kwargs.pop("source_type", "manual_text"),
        title=kwargs.pop("title", "Test Source"),
        content_text=kwargs.pop("content_text", "Some content"),
        status=kwargs.pop("status", "ready"),
        **kwargs,
    )
    db.add(source)
    db.flush()
    db.refresh(source)
    return source


# ── KnowledgeSource file fields ───────────────────────────────────────────────

def test_source_can_be_created_with_file_fields(db: Session, workspace_a: Workspace):
    kb = _make_kb(db, workspace_a)
    source = _make_source(
        db, workspace_a, kb,
        source_type="txt",
        title="My TXT",
        content_text="Extracted text content",
        original_filename="document.txt",
        mime_type="text/plain",
        file_size_bytes=1024,
        storage_provider="local",
        storage_key="workspaces/abc/sources/xyz/original/document.txt",
        content_hash="a" * 64,
    )
    db.commit()
    db.refresh(source)

    assert source.original_filename == "document.txt"
    assert source.mime_type == "text/plain"
    assert source.file_size_bytes == 1024
    assert source.storage_provider == "local"
    assert source.storage_key == "workspaces/abc/sources/xyz/original/document.txt"
    assert source.content_hash == "a" * 64


def test_manual_text_source_has_null_file_fields(db: Session, workspace_a: Workspace):
    kb = _make_kb(db, workspace_a)
    source = _make_source(db, workspace_a, kb)
    db.commit()
    db.refresh(source)

    assert source.original_filename is None
    assert source.mime_type is None
    assert source.file_size_bytes is None
    assert source.storage_provider is None
    assert source.storage_key is None
    assert source.content_hash is None


def test_knowledge_source_out_serializes_file_fields(db: Session, workspace_a: Workspace):
    kb = _make_kb(db, workspace_a)
    source = _make_source(
        db, workspace_a, kb,
        source_type="pdf_simple",
        title="Report",
        content_text="PDF text",
        original_filename="report.pdf",
        mime_type="application/pdf",
        file_size_bytes=204800,
        storage_provider="local",
        storage_key="workspaces/ws1/kb1/sources/src1/original/report.pdf",
        content_hash="b" * 64,
    )
    db.commit()
    db.refresh(source)

    out = KnowledgeSourceOut.model_validate(source)

    assert out.original_filename == "report.pdf"
    assert out.mime_type == "application/pdf"
    assert out.file_size_bytes == 204800
    assert out.storage_provider == "local"
    assert out.storage_key == "workspaces/ws1/kb1/sources/src1/original/report.pdf"
    assert out.content_hash == "b" * 64


def test_knowledge_source_out_null_fields_for_manual_text(db: Session, workspace_a: Workspace):
    kb = _make_kb(db, workspace_a)
    source = _make_source(db, workspace_a, kb)
    db.commit()
    db.refresh(source)

    out = KnowledgeSourceOut.model_validate(source)

    assert out.original_filename is None
    assert out.mime_type is None
    assert out.file_size_bytes is None
    assert out.storage_provider is None
    assert out.storage_key is None
    assert out.content_hash is None


def test_file_size_bytes_accepts_large_values(db: Session, workspace_a: Workspace):
    kb = _make_kb(db, workspace_a)
    # 50 MB — within enterprise plan limit
    source = _make_source(db, workspace_a, kb, file_size_bytes=52_428_800)
    db.commit()
    db.refresh(source)
    assert source.file_size_bytes == 52_428_800


def test_all_file_fields_can_be_updated(db: Session, workspace_a: Workspace):
    kb = _make_kb(db, workspace_a)
    source = _make_source(db, workspace_a, kb)
    db.commit()

    source.original_filename = "updated.csv"
    source.mime_type = "text/csv"
    source.file_size_bytes = 512
    source.storage_provider = "local"
    source.storage_key = "workspaces/x/sources/y/original/updated.csv"
    source.content_hash = "c" * 64
    db.commit()
    db.refresh(source)

    assert source.original_filename == "updated.csv"
    assert source.mime_type == "text/csv"
    assert source.content_hash == "c" * 64


# ── Plan.max_file_size_bytes ──────────────────────────────────────────────────

def test_plan_model_has_max_file_size_bytes_field(db: Session):
    plan = Plan(
        code=f"test-plan-{uuid.uuid4().hex[:6]}",
        name="Test Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=1,
        knowledge_bases_limit=1,
        sources_per_kb_limit=10,
        max_source_chars=50000,
        users_limit=3,
        pipelines_limit=1,
        integrations_limit=0,
        monthly_ai_credits=100,
        monthly_conversations=100,
        is_active=True,
        max_file_size_bytes=5_242_880,  # 5 MB
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    assert plan.max_file_size_bytes == 5_242_880


def test_plan_max_file_size_bytes_can_be_null(db: Session):
    plan = Plan(
        code=f"test-plan-null-{uuid.uuid4().hex[:6]}",
        name="No Limit Plan",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=99,
        knowledge_bases_limit=99,
        sources_per_kb_limit=99,
        max_source_chars=999999,
        users_limit=99,
        pipelines_limit=99,
        integrations_limit=99,
        monthly_ai_credits=9999,
        monthly_conversations=9999,
        is_active=True,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    assert plan.max_file_size_bytes is None


def test_migration_set_correct_limits_for_existing_plans(db: Session):
    expected = {
        "starter":     2_097_152,
        "growth":     10_485_760,
        "scale":      26_214_400,
        "enterprise": 52_428_800,
    }
    for code, expected_limit in expected.items():
        plan = db.query(Plan).filter_by(code=code).first()
        if plan is None:
            pytest.skip(f"Plan '{code}' not seeded in test DB — skipping limit check.")
        assert plan.max_file_size_bytes == expected_limit, (
            f"Plan '{code}': expected {expected_limit}, got {plan.max_file_size_bytes}"
        )
