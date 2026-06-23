import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_source import KnowledgeSource
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.knowledge_source import KnowledgeSourceCreate


def list_sources(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> list[KnowledgeSource]:
    _get_kb_or_404(db, workspace_id, kb_id)
    return list(
        db.scalars(
            select(KnowledgeSource)
            .where(
                KnowledgeSource.workspace_id == workspace_id,
                KnowledgeSource.knowledge_base_id == kb_id,
                KnowledgeSource.status != "archived",
            )
            .order_by(KnowledgeSource.created_at.desc())
        ).all()
    )


def create_source(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    user_id: uuid.UUID,
    data: KnowledgeSourceCreate,
) -> KnowledgeSource:
    _get_kb_or_404(db, workspace_id, kb_id)

    plan = _get_workspace_plan(db, workspace_id)
    _check_source_limit(db, kb_id, plan)

    content_text, metadata_json = _prepare_content(data, plan)

    source = KnowledgeSource(
        workspace_id=workspace_id,
        knowledge_base_id=kb_id,
        source_type=data.source_type,
        title=data.title,
        content_text=content_text,
        status="pending",
        metadata_json=metadata_json,
        created_by_user_id=user_id,
    )
    db.add(source)
    db.flush()

    # Phase 4.1: no async processing — mark ready immediately.
    # Phase 4.2 will replace this with actual chunking + embedding.
    try:
        source.status = "ready"
        source.processed_at = datetime.now(timezone.utc)
        source.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(source)
    except Exception as exc:
        source.status = "failed"
        source.error_message = str(exc)[:500]
        source.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(source)

    return source


def get_source_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
) -> KnowledgeSource:
    _get_kb_or_404(db, workspace_id, kb_id)
    source = db.scalar(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.workspace_id == workspace_id,
            KnowledgeSource.knowledge_base_id == kb_id,
            KnowledgeSource.status != "archived",
        )
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found.",
        )
    return source


def archive_source(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    source_id: uuid.UUID,
) -> KnowledgeSource:
    source = get_source_or_404(db, workspace_id, kb_id, source_id)
    source.status = "archived"
    source.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(source)
    return source


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_kb_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> KnowledgeBase:
    """Return the KB if it exists and belongs to the workspace. 404 otherwise.

    Archived KBs are treated as non-existent — consistent with the KB CRUD policy.
    Creating sources in an archived KB is blocked because archived KBs return 404.
    """
    kb = db.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.status != "archived",
        )
    )
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )
    return kb


def _check_source_limit(
    db: Session,
    kb_id: uuid.UUID,
    plan: Plan | None,
) -> None:
    if plan is None:
        return

    active_count = db.scalar(
        select(func.count()).where(
            KnowledgeSource.knowledge_base_id == kb_id,
            KnowledgeSource.status != "archived",
        )
    ) or 0

    if active_count >= plan.sources_per_kb_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Source limit reached for this knowledge base "
                f"({plan.sources_per_kb_limit} allowed). "
                "Archive an existing source or upgrade your plan."
            ),
        )


def _prepare_content(
    data: KnowledgeSourceCreate,
    plan: Plan | None,
) -> tuple[str, dict | None]:
    """Return (content_text, metadata_json) ready for storage."""
    max_chars = plan.max_source_chars if plan else 50_000
    metadata_json: dict | None = None

    if data.metadata:
        meta_dict = data.metadata.model_dump(exclude_none=True)
        if meta_dict:
            metadata_json = meta_dict

    if data.source_type == "faq_qa" and (
        data.metadata is not None
        and data.metadata.qa_pairs is not None
        and len(data.metadata.qa_pairs) > 0
    ):
        pairs = data.metadata.qa_pairs
        content_text = "\n\n".join(
            f"Pergunta: {p.question}\nResposta: {p.answer}" for p in pairs
        )
        # Always preserve original pairs in metadata_json for faq_qa
        metadata_json = {
            **(metadata_json or {}),
            "qa_pairs": [{"question": p.question, "answer": p.answer} for p in pairs],
        }
    else:
        content_text = (data.content_text or "").strip()

    if len(content_text) > max_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Source content exceeds the maximum allowed size of "
                f"{max_chars:,} characters for your plan."
            ),
        )

    return content_text, metadata_json


def _get_workspace_plan(db: Session, workspace_id: uuid.UUID) -> Plan | None:
    from app.enums import SubscriptionStatus

    sub = db.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id,
            WorkspaceSubscription.status == SubscriptionStatus.active.value,
        )
    )
    if sub is None:
        return None
    return db.scalar(select(Plan).where(Plan.id == sub.plan_id))
