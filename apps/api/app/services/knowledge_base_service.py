import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.agent_knowledge_base import AgentKnowledgeBase
from app.models.knowledge_base import KnowledgeBase
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseUpdate


def list_knowledge_bases(db: Session, workspace_id: uuid.UUID) -> list[KnowledgeBase]:
    return list(
        db.scalars(
            select(KnowledgeBase)
            .where(
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.status != "archived",
            )
            .order_by(KnowledgeBase.created_at.desc())
        ).all()
    )


def create_knowledge_base(
    db: Session,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: KnowledgeBaseCreate,
) -> KnowledgeBase:
    _check_kb_limit(db, workspace_id)
    kb = KnowledgeBase(
        workspace_id=workspace_id,
        name=data.name,
        description=data.description,
        status="active",
        created_by_user_id=user_id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


def get_knowledge_base_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> KnowledgeBase:
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
            detail="Base de conhecimento não encontrada.",
        )
    return kb


def update_knowledge_base(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
    data: KnowledgeBaseUpdate,
) -> KnowledgeBase:
    kb = get_knowledge_base_or_404(db, workspace_id, kb_id)

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        return kb

    for field, value in payload.items():
        setattr(kb, field, value)

    kb.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(kb)
    return kb


def archive_knowledge_base(
    db: Session,
    workspace_id: uuid.UUID,
    kb_id: uuid.UUID,
) -> KnowledgeBase:
    kb = get_knowledge_base_or_404(db, workspace_id, kb_id)

    kb.status = "archived"
    kb.updated_at = datetime.now(timezone.utc)

    # Deactivate all agent connections to this KB in the same transaction.
    db.execute(
        update(AgentKnowledgeBase)
        .where(AgentKnowledgeBase.knowledge_base_id == kb_id)
        .values(is_active=False, updated_at=datetime.now(timezone.utc))
    )

    db.commit()
    db.refresh(kb)
    return kb


# ── Plan limit helpers ────────────────────────────────────────────────────────

def _check_kb_limit(db: Session, workspace_id: uuid.UUID) -> None:
    plan = _get_workspace_plan(db, workspace_id)
    if plan is None:
        return

    active_count = db.scalar(
        select(func.count()).where(
            KnowledgeBase.workspace_id == workspace_id,
            KnowledgeBase.status != "archived",
        )
    ) or 0

    if active_count >= plan.knowledge_bases_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Limite de bases de conhecimento do seu plano atingido "
                f"({plan.knowledge_bases_limit} permitida(s)). "
                "Faça upgrade do plano ou arquive uma base de conhecimento existente."
            ),
        )


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
