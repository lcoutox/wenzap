import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import AgentStatus

ResponseStyle = Literal["concise", "balanced", "detailed"]
LanguageMode = Literal["auto", "pt", "en", "es"]
ContextTier = Literal["economical", "standard", "broad", "advanced", "maximum"]
KnowledgeFallback = Literal["ask_context", "direct_to_team", "knowledge_general"]

# ── Guided instructions types ─────────────────────────────────────────────────

GuidedRole = Literal[
    "initial_support", "consultive_sales", "presales_qualification",
    "customer_support", "relationship_postsale", "reception_triage", "custom"
]
GuidedPosture = Literal["consultive", "direct", "educational", "welcoming", "technical"]
GuidedInitiative = Literal["only_respond", "respond_suggest", "drive_conversion"]
GuidedWhenNoInfo = Literal["ask_context", "direct_to_team", "knowledge_only"]
InstructionsMode = Literal["guided", "advanced"]


class GuidedDoItem(str, Enum):
    answer_company_questions = "answer_company_questions"
    explain_products         = "explain_products"
    qualify_leads            = "qualify_leads"
    recommend_catalog        = "recommend_catalog"
    guide_next_step          = "guide_next_step"
    ask_context              = "ask_context"
    use_knowledge_base       = "use_knowledge_base"


class GuidedDontItem(str, Enum):
    no_fake_prices             = "no_fake_prices"
    no_fake_discounts          = "no_fake_discounts"
    no_guarantee_results       = "no_guarantee_results"
    no_fake_integrations       = "no_fake_integrations"
    no_official_partner_claims = "no_official_partner_claims"
    no_sensitive_data          = "no_sensitive_data"
    no_out_of_scope            = "no_out_of_scope"


class GuidedConfigSchema(BaseModel):
    role:                  GuidedRole | None = None
    main_objective:        str | None = Field(default=None, max_length=500)
    posture:               GuidedPosture | None = None
    initiative:            GuidedInitiative | None = None
    when_no_info:          GuidedWhenNoInfo | None = None
    do_items:              list[GuidedDoItem] = Field(default_factory=list)
    custom_should_do:      list[str] = Field(default_factory=list)
    dont_items:            list[GuidedDontItem] = Field(default_factory=list)
    custom_should_not_do:  list[str] = Field(default_factory=list)
    extra_restrictions:    str | None = Field(default=None, max_length=1000)
    good_response_example: str | None = Field(default=None, max_length=2000)
    bad_response_example:  str | None = Field(default=None, max_length=2000)
    model_config = ConfigDict(use_enum_values=True)

    @field_validator("custom_should_do", "custom_should_not_do", mode="before")
    @classmethod
    def validate_custom_items(cls, v: list | None) -> list:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("Must be a list of strings.")
        result = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("Each item must be a string.")
            stripped = item.strip()
            if stripped:
                if len(stripped) > 500:
                    raise ValueError("Each custom item must be at most 500 characters.")
                result.append(stripped)
        return result


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str | None = None
    persona: str | None = None
    ai_model_id: uuid.UUID
    temperature: float = 0.7
    catalog_enabled: bool = False
    response_style: ResponseStyle = "balanced"
    language_mode: LanguageMode = "auto"
    knowledge_only: bool = False
    show_sources: bool = False
    knowledge_fallback: KnowledgeFallback | None = None
    instructions_mode: InstructionsMode = "guided"
    guided_config: GuidedConfigSchema | None = None

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name must not be empty.")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters.")
        return v

    @field_validator("system_prompt")
    @classmethod
    def system_prompt_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 8000:
            raise ValueError("System prompt must be at most 8000 characters.")
        return v

    @field_validator("persona")
    @classmethod
    def persona_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 1000:
            raise ValueError("Persona must be at most 1000 characters.")
        return v

    @field_validator("temperature")
    @classmethod
    def temperature_must_be_in_range(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0.")
        return v


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    persona: str | None = None
    ai_model_id: uuid.UUID | None = None
    temperature: float | None = None
    catalog_enabled: bool | None = None
    response_style: ResponseStyle | None = None
    language_mode: LanguageMode | None = None
    knowledge_only: bool | None = None
    show_sources: bool | None = None
    knowledge_fallback: KnowledgeFallback | None = None
    instructions_mode: InstructionsMode | None = None
    guided_config: GuidedConfigSchema | None = None
    advanced_prompt: str | None = Field(default=None, max_length=20000)
    context_tier: ContextTier | None = None
    reply_delay_seconds: int | None = None

    @field_validator("reply_delay_seconds")
    @classmethod
    def validate_reply_delay(cls, v: int | None) -> int | None:
        if v is not None and v not in {0, 3, 5, 8, 15}:
            raise ValueError("reply_delay_seconds must be one of: 0, 3, 5, 8, 15.")
        return v

    @field_validator("name")
    @classmethod
    def name_must_be_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Name must not be empty.")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters.")
        return v

    @field_validator("system_prompt")
    @classmethod
    def system_prompt_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 8000:
            raise ValueError("System prompt must be at most 8000 characters.")
        return v

    @field_validator("persona")
    @classmethod
    def persona_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 1000:
            raise ValueError("Persona must be at most 1000 characters.")
        return v

    @field_validator("temperature")
    @classmethod
    def temperature_must_be_in_range(cls, v: float | None) -> float | None:
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("temperature must be between 0.0 and 1.0.")
        return v


class AgentStatusUpdate(BaseModel):
    status: AgentStatus


class AgentOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None
    status: AgentStatus
    system_prompt: str | None
    persona: str | None
    ai_model_id: uuid.UUID | None
    model_name: str
    temperature: float
    catalog_enabled: bool
    response_style: ResponseStyle
    language_mode: LanguageMode
    knowledge_only: bool
    show_sources: bool
    knowledge_fallback: str | None
    instructions_mode: str
    guided_config: dict | None
    advanced_prompt: str | None
    context_tier: str
    reply_delay_seconds: int
    avatar_url: str | None
    avatar_mime_type: str | None
    avatar_updated_at: datetime | None
    default_pipeline_id: uuid.UUID | None = None
    default_pipeline_stage_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
