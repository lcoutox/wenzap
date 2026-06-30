import uuid
from typing import Literal

from pydantic import BaseModel


class AgentCatalogScopeOut(BaseModel):
    catalog_enabled: bool
    category_scope: Literal["all", "selected"]
    category_ids: list[uuid.UUID]

    model_config = {"from_attributes": True}


class AgentCatalogScopeUpdate(BaseModel):
    catalog_enabled: bool
    category_scope: Literal["all", "selected"] = "all"
    category_ids: list[uuid.UUID] = []
