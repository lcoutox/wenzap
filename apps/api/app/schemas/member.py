import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import MemberRole, MemberStatus


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    name: str
    avatar_url: str | None
    role: MemberRole
    status: MemberStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberRoleUpdate(BaseModel):
    role: MemberRole
