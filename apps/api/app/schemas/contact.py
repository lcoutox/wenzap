import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    email: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=50)
    external_id: str | None = Field(default=None, max_length=300)
    # Stored as metadata_json on the model.
    metadata: dict | None = None


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    email: str | None = None
    phone: str | None = None
    external_id: str | None = None
    metadata: dict | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_name(cls, values: dict) -> dict:
        # name=null in the JSON body must be rejected — a contact cannot have no name.
        # We distinguish "field absent" (not in dict) from "field present as null".
        if isinstance(values, dict) and "name" in values and values["name"] is None:
            raise ValueError("name cannot be set to null")
        return values


class ContactOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    email: str | None
    phone: str | None
    external_id: str | None
    metadata_json: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
