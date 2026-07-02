import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContactCreate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=50)
    origin: str | None = Field(default=None, max_length=100)
    external_id: str | None = Field(default=None, max_length=300)
    metadata: dict | None = None

    @model_validator(mode="after")
    def require_at_least_one_identifier(self) -> "ContactCreate":
        if not self.name and not self.email and not self.phone:
            raise ValueError("Informe pelo menos nome, e-mail ou telefone.")
        return self


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    email: str | None = None
    phone: str | None = None
    origin: str | None = None
    external_id: str | None = None
    metadata: dict | None = None


class ContactOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str | None
    email: str | None
    phone: str | None
    origin: str | None
    last_seen_at: datetime | None
    external_id: str | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactListOut(BaseModel):
    items: list[ContactOut]
    total: int
    limit: int
    offset: int


class ContactVariableCreate(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1)
    source: str | None = Field(default=None, max_length=100)


class ContactVariableUpdate(BaseModel):
    value: str = Field(min_length=1)
    source: str | None = None


class ContactVariableOut(BaseModel):
    id: uuid.UUID
    contact_id: uuid.UUID
    workspace_id: uuid.UUID
    key: str
    value: str
    source: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
