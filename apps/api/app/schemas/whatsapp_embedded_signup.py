"""
Schemas for WhatsApp Embedded Signup endpoints — ES.2.

State endpoint:    POST /channels/whatsapp/embedded-signup/state
Exchange endpoint: POST /channels/whatsapp/embedded-signup/exchange
"""

import re
import uuid

from pydantic import BaseModel, Field, field_validator

_NUMERIC_RE = re.compile(r"^\d+$")


def _validate_numeric_id(v: str, field_name: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError(f"{field_name} must not be empty")
    if not _NUMERIC_RE.match(v):
        raise ValueError(f"{field_name} must be a numeric string (Meta ID)")
    return v


# ── State ─────────────────────────────────────────────────────────────────────


class WhatsAppEmbeddedSignupStateRequest(BaseModel):
    agent_id: uuid.UUID


class WhatsAppEmbeddedSignupStateOut(BaseModel):
    state: str
    expires_in: int = 600  # seconds


# ── Exchange ──────────────────────────────────────────────────────────────────


class WhatsAppEmbeddedSignupExchangeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    state: str = Field(min_length=1, max_length=512)
    # Provided by the WA_EMBEDDED_SIGNUP postMessage from the Meta popup.
    # No redirect_uri is passed — the JS SDK handles the popup redirect internally.
    waba_id: str = Field(min_length=1, max_length=100)
    phone_number_id: str = Field(min_length=1, max_length=100)
    business_id: str | None = Field(default=None, max_length=100)

    @field_validator("waba_id")
    @classmethod
    def validate_waba_id(cls, v: str) -> str:
        return _validate_numeric_id(v, "waba_id")

    @field_validator("phone_number_id")
    @classmethod
    def validate_phone_number_id(cls, v: str) -> str:
        return _validate_numeric_id(v, "phone_number_id")

    @field_validator("business_id")
    @classmethod
    def validate_business_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_numeric_id(v, "business_id")
