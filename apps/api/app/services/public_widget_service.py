"""
Public widget service — no Clerk authentication.

All operations are scoped by public_key (resolved to a Channel internally).
Visitors never supply workspace_id or agent_id directly.
"""

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.widget_session import WidgetSession
from app.schemas.conversation_message import ConversationMessageCreate
from app.schemas.public_widget import (
    PublicWidgetConfigOut,
    PublicWidgetMessageCreate,
    PublicWidgetMessageOut,
    WidgetSessionOut,
)

_SESSION_TOKEN_PREFIX = "wss_"
_SESSION_TOKEN_MAX_RETRIES = 5

# Default values for WebWidgetConfig fields in case config_json is incomplete.
_CONFIG_DEFAULTS: dict = {
    "theme": "dark",
    "primary_color": "#6366f1",
    "position": "bottom-right",
    "welcome_message": "Olá! Como posso ajudar?",
    "header_title": "Atendimento",
    "header_subtitle": "Resposta em segundos",
    "placeholder": "Digite sua mensagem...",
    "avatar_url": None,
    "auto_open": False,
    "auto_open_delay_seconds": 3,
}


def is_origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    """
    Return True if the request origin is permitted for this channel.

    Rules:
    - allowed_origins empty → any origin (and absent Origin header) is allowed.
    - allowed_origins non-empty → Origin header must be present and match exactly.
    """
    if not allowed_origins:
        return True
    if origin is None:
        return False
    return origin in allowed_origins


def _resolve_active_web_widget(db: Session, public_key: str) -> Channel:
    """
    Resolve a public_key to an active web_widget Channel.
    Always returns 404 for invalid/inactive/archived to prevent enumeration.
    """
    channel = db.scalar(
        select(Channel).where(
            Channel.public_key == public_key,
            Channel.channel_type == "web_widget",
            Channel.status == "active",
        )
    )
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found.",
        )
    return channel


def _check_origin(channel: Channel, origin: str | None) -> None:
    if not is_origin_allowed(origin, channel.allowed_origins or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed.",
        )


def get_public_widget_config(
    db: Session,
    public_key: str,
    origin: str | None,
) -> PublicWidgetConfigOut:
    channel = _resolve_active_web_widget(db, public_key)
    _check_origin(channel, origin)

    cfg: dict = {**_CONFIG_DEFAULTS, **(channel.config_json or {})}

    return PublicWidgetConfigOut(
        public_key=channel.public_key,
        name=channel.name,
        theme=cfg.get("theme", _CONFIG_DEFAULTS["theme"]),
        primary_color=cfg.get("primary_color", _CONFIG_DEFAULTS["primary_color"]),
        position=cfg.get("position", _CONFIG_DEFAULTS["position"]),
        welcome_message=cfg.get("welcome_message", _CONFIG_DEFAULTS["welcome_message"]),
        header_title=cfg.get("header_title", _CONFIG_DEFAULTS["header_title"]),
        header_subtitle=cfg.get("header_subtitle", _CONFIG_DEFAULTS["header_subtitle"]),
        placeholder=cfg.get("placeholder", _CONFIG_DEFAULTS["placeholder"]),
        avatar_url=cfg.get("avatar_url"),
        auto_open=cfg.get("auto_open", _CONFIG_DEFAULTS["auto_open"]),
        auto_open_delay_seconds=cfg.get(
            "auto_open_delay_seconds", _CONFIG_DEFAULTS["auto_open_delay_seconds"]
        ),
    )


def _generate_session_token() -> str:
    return _SESSION_TOKEN_PREFIX + secrets.token_urlsafe(32)


def _create_anonymous_contact(db: Session, channel: Channel) -> Contact:
    contact = Contact(
        workspace_id=channel.workspace_id,
        name="Visitante",
        metadata_json={
            "source": "web_widget",
            "channel_id": str(channel.id),
            "public_key": channel.public_key,
        },
    )
    db.add(contact)
    db.flush()
    return contact


def _create_widget_conversation(
    db: Session, channel: Channel, contact: Contact
) -> Conversation:
    conv = Conversation(
        workspace_id=channel.workspace_id,
        contact_id=contact.id,
        agent_id=channel.agent_id,
        channel_type="web_widget",
        status="open",
        ai_enabled=True,
        assigned_user_id=None,
    )
    db.add(conv)
    db.flush()
    return conv


def _create_new_session(db: Session, channel: Channel) -> WidgetSession:
    contact = _create_anonymous_contact(db, channel)
    conv = _create_widget_conversation(db, channel, contact)

    for _ in range(_SESSION_TOKEN_MAX_RETRIES):
        token = _generate_session_token()
        session = WidgetSession(
            channel_id=channel.id,
            workspace_id=channel.workspace_id,
            contact_id=contact.id,
            conversation_id=conv.id,
            session_token=token,
        )
        db.add(session)
        try:
            db.commit()
            db.refresh(session)
            return session
        except IntegrityError as exc:
            db.rollback()
            if "uq_widget_sessions_session_token" in str(exc.orig) or \
               "widget_sessions_session_token" in str(exc.orig):
                # Extremely rare collision — regenerate token and retry.
                # Re-add the contact and conversation that were rolled back.
                contact = _create_anonymous_contact(db, channel)
                conv = _create_widget_conversation(db, channel, contact)
                continue
            raise

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to generate a unique session token. Please try again.",
    )


def create_or_resume_widget_session(
    db: Session,
    public_key: str,
    origin: str | None,
    session_token: str | None,
) -> WidgetSessionOut:
    channel = _resolve_active_web_widget(db, public_key)
    _check_origin(channel, origin)

    # Try to resume an existing session if the visitor supplied a token.
    if session_token:
        existing = db.scalar(
            select(WidgetSession).where(
                WidgetSession.session_token == session_token,
                WidgetSession.channel_id == channel.id,
                WidgetSession.workspace_id == channel.workspace_id,
            )
        )
        if existing:
            existing.last_seen_at = datetime.now(timezone.utc)
            db.commit()
            return WidgetSessionOut(session_token=existing.session_token)
        # Token supplied but not found for this channel → create fresh session.
        # This handles: expired localStorage, wrong channel, cross-channel tokens.

    new_session = _create_new_session(db, channel)
    return WidgetSessionOut(session_token=new_session.session_token)


# ── Visible directions for widget visitors ────────────────────────────────────
# Visitors see external messages only: their own (customer), agent replies, and
# any human operator responses. Internal notes and system messages are hidden.
_PUBLIC_VISIBLE_DIRECTIONS_SENDERS: set[tuple[str, str]] = {
    ("inbound",  "customer"),
    ("outbound", "agent"),
    ("outbound", "human"),
}


def _resolve_session_or_401(
    db: Session,
    channel: Channel,
    session_token: str | None,
) -> WidgetSession:
    """Resolve and validate a session token for the given channel."""
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Session-Token header is required.",
        )
    session = db.scalar(
        select(WidgetSession).where(
            WidgetSession.session_token == session_token,
            WidgetSession.channel_id == channel.id,
            WidgetSession.workspace_id == channel.workspace_id,
        )
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )
    return session


def send_widget_message(
    db: Session,
    public_key: str,
    origin: str | None,
    session_token: str | None,
    data: PublicWidgetMessageCreate,
) -> PublicWidgetMessageOut:
    channel = _resolve_active_web_widget(db, public_key)
    _check_origin(channel, origin)
    session = _resolve_session_or_401(db, channel, session_token)

    msg_data = ConversationMessageCreate(
        direction="inbound",
        sender_type="customer",
        content=data.content,
        content_type="text",
    )

    # Import locally to avoid circular dependency (message service imports
    # conversation service which has no dependency on this module).
    from app.services.conversation_message_service import create_message  # noqa: PLC0415

    msg = create_message(
        db=db,
        workspace_id=session.workspace_id,
        conversation_id=session.conversation_id,
        current_user_id=None,  # Public endpoint — no Clerk user.
        data=msg_data,
    )

    # Touch last_seen_at for the session.
    session.last_seen_at = datetime.now(timezone.utc)
    db.commit()

    return PublicWidgetMessageOut(
        id=msg.id,
        direction=msg.direction,
        sender_type=msg.sender_type,
        content=msg.content,
        created_at=msg.created_at,
    )


def list_widget_messages(
    db: Session,
    public_key: str,
    origin: str | None,
    session_token: str | None,
    limit: int = 50,
) -> list[PublicWidgetMessageOut]:
    channel = _resolve_active_web_widget(db, public_key)
    _check_origin(channel, origin)
    session = _resolve_session_or_401(db, channel, session_token)

    effective_limit = min(limit, 100)

    messages = db.scalars(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == session.conversation_id,
            ConversationMessage.workspace_id == session.workspace_id,
        )
        .order_by(ConversationMessage.created_at.asc())
        .limit(effective_limit)
    ).all()

    return [
        PublicWidgetMessageOut(
            id=m.id,
            direction=m.direction,
            sender_type=m.sender_type,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
        if (m.direction, m.sender_type) in _PUBLIC_VISIBLE_DIRECTIONS_SENDERS
    ]
