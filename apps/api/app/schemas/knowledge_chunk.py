import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeChunkOut(BaseModel):
    """Read-only schema for a knowledge chunk. Embedding vector is never returned."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_id: uuid.UUID
    chunk_index: int
    content: str
    char_count: int
    metadata_json: dict | None
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimension: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
