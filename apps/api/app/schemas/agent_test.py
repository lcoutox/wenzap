import uuid

from pydantic import BaseModel, field_validator


class AgentTestRequest(BaseModel):
    message: str
    session_id: uuid.UUID | None = None

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v:
            raise ValueError("message must not be empty")
        if len(v) > 4000:
            raise ValueError("message must not exceed 4000 characters")
        return v


class AgentTestModelInfo(BaseModel):
    display_name: str
    provider: str
    model_name: str


class AgentTestResponse(BaseModel):
    reply: str
    credits_used: int
    input_tokens: int
    output_tokens: int
    duration_ms: int
    model: AgentTestModelInfo
    session_id: uuid.UUID
    # RAG metadata (Phase 4.3) — optional fields with safe defaults so existing
    # clients that ignore unknown fields continue to work without changes.
    rag_used: bool = False
    retrieved_chunks_count: int = 0
