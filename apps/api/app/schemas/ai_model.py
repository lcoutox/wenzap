import uuid

from pydantic import BaseModel


class AiModelOut(BaseModel):
    id: uuid.UUID
    code: str
    display_name: str
    description: str | None
    model_name: str
    credits_per_message: int
    min_plan_code: str
    context_window_tokens: int | None
    is_default: bool
    is_recommended: bool
    is_featured: bool
    supports_vision: bool
    supports_tools: bool
    supports_reasoning: bool
    supports_code: bool
    available: bool  # computed from workspace plan

    model_config = {"from_attributes": True}


class AiModelProviderOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    logo_url: str | None
    models: list[AiModelOut]

    model_config = {"from_attributes": True}


class AiCatalogOut(BaseModel):
    current_plan: str
    providers: list[AiModelProviderOut]
