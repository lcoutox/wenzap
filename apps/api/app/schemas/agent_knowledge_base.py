import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentKnowledgeBaseCreate(BaseModel):
    knowledge_base_id: uuid.UUID


class AgentKnowledgeBaseUpdate(BaseModel):
    is_active: bool


class AgentKnowledgeBaseOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    agent_id: uuid.UUID
    knowledge_base_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Embedded KB summary to avoid extra round-trips from the frontend
    knowledge_base_name: str
    knowledge_base_status: str

    model_config = ConfigDict(from_attributes=False)
