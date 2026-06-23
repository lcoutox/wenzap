import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QaPair(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)


class SourceMetadata(BaseModel):
    source_category: str | None = None
    qa_pairs: list[QaPair] | None = None


class KnowledgeSourceCreate(BaseModel):
    source_type: Literal["manual_text", "faq_qa"]
    title: str = Field(min_length=1, max_length=300)
    content_text: str | None = None
    metadata: SourceMetadata | None = None

    @model_validator(mode="after")
    def validate_by_type(self) -> "KnowledgeSourceCreate":
        if self.source_type == "manual_text":
            if not self.content_text or not self.content_text.strip():
                raise ValueError(
                    "content_text is required and must not be empty for manual_text sources."
                )
        elif self.source_type == "faq_qa":
            has_content = self.content_text and self.content_text.strip()
            has_pairs = (
                self.metadata is not None
                and self.metadata.qa_pairs is not None
                and len(self.metadata.qa_pairs) > 0
            )
            if not has_content and not has_pairs:
                raise ValueError(
                    "faq_qa sources require either content_text or metadata.qa_pairs "
                    "with at least one pair."
                )
        return self


class KnowledgeSourceOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_type: str
    title: str
    content_text: str | None
    status: str
    metadata_json: dict | None
    error_message: str | None
    created_by_user_id: uuid.UUID | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # File upload fields (Phase 4.4) — None for manual_text / faq_qa sources
    original_filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    storage_provider: str | None = None
    storage_key: str | None = None
    content_hash: str | None = None

    model_config = ConfigDict(from_attributes=True)
