import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.schemas.channel import ChannelCreate, ChannelOut, ChannelUpdate, _parse_config_by_type

_MAX_LIMIT = 100
_PUBLIC_KEY_MAX_RETRIES = 5

_PUBLIC_KEY_PREFIXES: dict[str, str] = {
    "web_widget": "wgt_",
    "whatsapp": "wap_",
}
_PUBLIC_KEY_DEFAULT_PREFIX = "ch_"


def _generate_public_key(channel_type: str) -> str:
    prefix = _PUBLIC_KEY_PREFIXES.get(channel_type, _PUBLIC_KEY_DEFAULT_PREFIX)
    return prefix + secrets.token_urlsafe(18)


def _channel_to_out(channel: Channel) -> ChannelOut:
    return ChannelOut.from_orm(channel)


def _resolve_agent_or_404(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID
) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found in this workspace.",
        )
    return agent


def list_channels(
    db: Session,
    workspace_id: uuid.UUID,
    channel_type: str | None = None,
    agent_id: uuid.UUID | None = None,
    include_archived: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> list[ChannelOut]:
    effective_limit = min(limit, _MAX_LIMIT)
    q = select(Channel).where(Channel.workspace_id == workspace_id)
    if not include_archived:
        q = q.where(Channel.status != "archived")
    if channel_type is not None:
        q = q.where(Channel.channel_type == channel_type)
    if agent_id is not None:
        q = q.where(Channel.agent_id == agent_id)
    q = q.order_by(Channel.created_at.desc()).offset(skip).limit(effective_limit)
    channels = list(db.scalars(q).all())
    return [_channel_to_out(c) for c in channels]


def create_channel(
    db: Session,
    workspace_id: uuid.UUID,
    data: ChannelCreate,
) -> ChannelOut:
    _resolve_agent_or_404(db, workspace_id, data.agent_id)

    for _ in range(_PUBLIC_KEY_MAX_RETRIES):
        public_key = _generate_public_key(data.channel_type)
        channel = Channel(
            workspace_id=workspace_id,
            agent_id=data.agent_id,
            channel_type=data.channel_type,
            name=data.name,
            public_key=public_key,
            status="active",
            config_json=data.config,
            allowed_origins=data.allowed_origins,
        )
        db.add(channel)
        try:
            db.commit()
            db.refresh(channel)
            return _channel_to_out(channel)
        except IntegrityError as exc:
            db.rollback()
            if "ix_channels_public_key" in str(exc.orig) or "channels_public_key" in str(exc.orig):
                continue
            raise

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate a unique public key. Please try again.",
    )


def get_channel_or_404(
    db: Session,
    workspace_id: uuid.UUID,
    channel_id: uuid.UUID,
) -> Channel:
    channel = db.scalar(
        select(Channel).where(
            Channel.id == channel_id,
            Channel.workspace_id == workspace_id,
        )
    )
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found.",
        )
    return channel


def get_channel_detail(
    db: Session,
    workspace_id: uuid.UUID,
    channel_id: uuid.UUID,
) -> ChannelOut:
    return _channel_to_out(get_channel_or_404(db, workspace_id, channel_id))


def update_channel(
    db: Session,
    workspace_id: uuid.UUID,
    channel_id: uuid.UUID,
    data: ChannelUpdate,
) -> ChannelOut:
    channel = get_channel_or_404(db, workspace_id, channel_id)

    if data.name is not None:
        channel.name = data.name
    if data.config is not None:
        try:
            channel.config_json = _parse_config_by_type(channel.channel_type, data.config)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    if data.allowed_origins is not None:
        channel.allowed_origins = data.allowed_origins
    if data.status is not None:
        channel.status = data.status

    channel.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(channel)
    return _channel_to_out(channel)


def archive_channel(
    db: Session,
    workspace_id: uuid.UUID,
    channel_id: uuid.UUID,
) -> ChannelOut:
    channel = get_channel_or_404(db, workspace_id, channel_id)
    channel.status = "archived"
    channel.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(channel)
    return _channel_to_out(channel)


def get_whatsapp_channel_by_phone_number_id(
    db: Session,
    phone_number_id: str,
) -> Channel | None:
    """
    Look up an active WhatsApp channel by its Meta phone_number_id.

    Used by the webhook receiver to route inbound messages to the correct workspace.
    Returns None (not an error) when no channel matches — the caller decides how to handle it.

    Tenant isolation: the returned Channel carries workspace_id, so the caller always
    knows which workspace owns the channel without any extra lookup.

    TODO: add a partial index for performance at scale:
      CREATE INDEX ON channels ((config_json->>'phone_number_id')) WHERE channel_type = 'whatsapp';
    """
    return db.scalar(
        select(Channel).where(
            Channel.channel_type == "whatsapp",
            Channel.status != "archived",
            Channel.config_json["phone_number_id"].astext == phone_number_id,
        )
    )
