import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import SubscriptionStatus
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.plan import Plan
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.ai_model import AiCatalogOut, AiModelOut, AiModelProviderOut

# Plan availability hierarchy — higher tier can access all lower-tier models
PLAN_TIER: dict[str, int] = {
    "starter":    1,
    "growth":     2,
    "scale":      3,
    "enterprise": 4,
}


def _get_workspace_plan_code(db: Session, workspace_id: uuid.UUID) -> str:
    """Returns plan.code for the active subscription of the workspace."""
    sub = db.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id,
            WorkspaceSubscription.status == SubscriptionStatus.active.value,
        )
    )
    if sub is None:
        return "starter"  # safe default — most restrictive

    plan = db.scalar(select(Plan).where(Plan.id == sub.plan_id))
    return plan.code if plan else "starter"


def _is_available(plan_code: str, model_min_plan: str) -> bool:
    workspace_tier = PLAN_TIER.get(plan_code, 1)
    model_tier = PLAN_TIER.get(model_min_plan, 1)
    return workspace_tier >= model_tier


def get_catalog(db: Session, workspace_id: uuid.UUID) -> AiCatalogOut:
    plan_code = _get_workspace_plan_code(db, workspace_id)

    ENABLED_PROVIDERS = {"anthropic", "openai"}

    providers = db.scalars(
        select(AiModelProvider)
        .where(
            AiModelProvider.is_active.is_(True),
            AiModelProvider.code.in_(ENABLED_PROVIDERS),
        )
        .order_by(AiModelProvider.name)
    ).all()

    result = []
    for provider in providers:
        models = db.scalars(
            select(AiModel)
            .where(AiModel.provider_id == provider.id, AiModel.is_active.is_(True))
            .order_by(AiModel.sort_order, AiModel.display_name)
        ).all()

        model_out = [
            AiModelOut(
                id=m.id,
                code=m.code,
                display_name=m.display_name,
                description=m.description,
                model_name=m.model_name,
                credits_per_message=m.credits_per_message,
                min_plan_code=m.min_plan_code,
                context_window_tokens=m.context_window_tokens,
                is_default=m.is_default,
                is_recommended=m.is_recommended,
                is_featured=m.is_featured,
                supports_vision=m.supports_vision,
                supports_tools=m.supports_tools,
                supports_reasoning=m.supports_reasoning,
                supports_code=m.supports_code,
                available=_is_available(plan_code, m.min_plan_code),
            )
            for m in models
        ]

        result.append(
            AiModelProviderOut(
                id=provider.id,
                code=provider.code,
                name=provider.name,
                description=provider.description,
                logo_url=provider.logo_url,
                models=model_out,
            )
        )

    return AiCatalogOut(current_plan=plan_code, providers=result)


def get_model_or_404(db: Session, model_id: uuid.UUID) -> AiModel:
    model = db.scalar(select(AiModel).where(AiModel.id == model_id, AiModel.is_active.is_(True)))
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Modelo de IA não encontrado ou inativo.",
        )
    return model


def validate_model_for_plan(model: AiModel, plan_code: str) -> None:
    if not _is_available(plan_code, model.min_plan_code):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"O modelo '{model.display_name}' requer o plano "
                f"'{model.min_plan_code}' ou superior."
            ),
        )
