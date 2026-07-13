"""Schemas for Evolution API provisioning endpoints — Slice 4.

POST /channels/whatsapp/evolution/connect            — create instance + QR
GET  /channels/whatsapp/evolution/{channel_id}/status — poll connection state
POST /channels/whatsapp/evolution/{channel_id}/disconnect
"""

import uuid

from pydantic import BaseModel

from app.schemas.channel import ChannelOut


class EvolutionConnectRequest(BaseModel):
    agent_id: uuid.UUID


class EvolutionConnectOut(BaseModel):
    channel: ChannelOut
    qrcode_base64: str | None = None
    pairing_code: str | None = None


class EvolutionStatusOut(BaseModel):
    channel_id: uuid.UUID
    state: str  # raw Evolution state: "open" | "connecting" | "close" | ...
