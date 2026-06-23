import uuid
from datetime import datetime

from pydantic import BaseModel


class PlaygroundMessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    agent_test_run_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaygroundSessionOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    agent_id: uuid.UUID
    user_id: uuid.UUID | None
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlaygroundSessionWithMessages(PlaygroundSessionOut):
    messages: list[PlaygroundMessageOut]


class PlaygroundSessionCreate(BaseModel):
    # Title is always set to "Nova conversa" on creation.
    # It is updated to the first user message on the first /test call (Iteration 3).
    pass
