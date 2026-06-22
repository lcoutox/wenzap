from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.ai_model import AiCatalogOut
from app.services.ai_model_service import get_catalog

router = APIRouter(prefix="/ai-models")


@router.get("", response_model=AiCatalogOut)
def list_ai_models(
    _: User = Depends(get_current_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> AiCatalogOut:
    return get_catalog(db, workspace.id)
