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

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.widget_session import WidgetSession
from app.schemas.conversation_message import ConversationMessageCreate
from app.schemas.public_widget import (
    ContactCaptureInput,
    PublicWidgetConfigOut,
    PublicWidgetMessageCreate,
    PublicWidgetMessageOut,
    WidgetPageContext,
    WidgetSessionOut,
)
from app.services.agent_avatar_service import get_avatar_url
from app.services.pipeline_service import ensure_conversation_pipeline_entry
from app.services.plan_service import count_new_conversation

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
    "auto_open": False,
    "auto_open_delay_seconds": 3,
    # Contact capture defaults
    "contact_capture_enabled": False,
    "require_name": False,
    "require_email": False,
    "require_phone": False,
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


def _get_cfg(channel: Channel) -> dict:
    return {**_CONFIG_DEFAULTS, **(channel.config_json or {})}


def _is_contact_captured(cfg: dict, contact: Contact) -> bool:
    """
    Returns True when contact_capture is satisfied for this session.

    True when:
    - contact_capture_enabled is False (capture not required), OR
    - All required fields are already filled in on the Contact.
    """
    if not cfg.get("contact_capture_enabled", False):
        return True
    if cfg.get("require_name") and not (contact.name and contact.name != "Visitante"):
        return False
    if cfg.get("require_email") and not contact.email:
        return False
    if cfg.get("require_phone") and not contact.phone:
        return False
    return True


def get_public_widget_config(
    db: Session,
    public_key: str,
    origin: str | None,
) -> PublicWidgetConfigOut:
    channel = _resolve_active_web_widget(db, public_key)
    _check_origin(channel, origin)

    cfg = _get_cfg(channel)

    agent = db.get(Agent, channel.agent_id) if channel.agent_id else None
    avatar_url = get_avatar_url(agent) if agent else None

    return PublicWidgetConfigOut(
        public_key=channel.public_key,
        name=channel.name,
        theme=cfg["theme"],
        primary_color=cfg["primary_color"],
        position=cfg["position"],
        welcome_message=cfg["welcome_message"],
        header_title=cfg["header_title"],
        header_subtitle=cfg["header_subtitle"],
        placeholder=cfg["placeholder"],
        avatar_url=avatar_url,
        auto_open=cfg["auto_open"],
        auto_open_delay_seconds=cfg["auto_open_delay_seconds"],
        contact_capture_enabled=cfg["contact_capture_enabled"],
        require_name=cfg["require_name"],
        require_email=cfg["require_email"],
        require_phone=cfg["require_phone"],
    )


def _generate_session_token() -> str:
    return _SESSION_TOKEN_PREFIX + secrets.token_urlsafe(32)


def _build_attribution(ctx: WidgetPageContext) -> dict:
    return {
        k: v
        for k, v in {
            "first_page_url": ctx.page_url,
            "first_page_title": ctx.page_title,
            "first_referrer": ctx.referrer,
            "utm_source": ctx.utm_source,
            "utm_medium": ctx.utm_medium,
            "utm_campaign": ctx.utm_campaign,
            "utm_term": ctx.utm_term,
            "utm_content": ctx.utm_content,
        }.items()
        if v is not None
    }


def _build_last_seen(ctx: WidgetPageContext) -> dict:
    return {
        k: v
        for k, v in {
            "page_url": ctx.page_url,
            "page_title": ctx.page_title,
            "referrer": ctx.referrer,
        }.items()
        if v is not None
    }


def _apply_attribution_to_contact(
    contact: Contact, ctx: WidgetPageContext, is_new: bool
) -> None:
    """
    Persist attribution data in Contact.metadata_json.
    - first_* fields: written only if not already present.
    - last_seen: always updated when page_context is provided.
    - UTM fields in attribution: only set if not already present.
    """
    meta: dict = dict(contact.metadata_json or {})

    attribution: dict = dict(meta.get("attribution", {}))
    new_attribution = _build_attribution(ctx)
    for k, v in new_attribution.items():
        if k not in attribution:
            attribution[k] = v

    last_seen = _build_last_seen(ctx)

    if attribution:
        meta["attribution"] = attribution
    if last_seen:
        meta["last_seen"] = last_seen

    contact.metadata_json = meta


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
    count_new_conversation(db, channel.workspace_id)
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
    ensure_conversation_pipeline_entry(db, conv)
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
    page_context: WidgetPageContext | None = None,
) -> WidgetSessionOut:
    channel = _resolve_active_web_widget(db, public_key)
    _check_origin(channel, origin)
    cfg = _get_cfg(channel)

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
            contact = db.get(Contact, existing.contact_id)
            if contact and page_context:
                _apply_attribution_to_contact(contact, page_context, is_new=False)
            db.commit()
            captured = _is_contact_captured(cfg, contact) if contact else True
            return WidgetSessionOut(
                session_token=existing.session_token,
                contact_captured=captured,
            )

    new_session = _create_new_session(db, channel)
    contact = db.get(Contact, new_session.contact_id)
    if contact and page_context:
        _apply_attribution_to_contact(contact, page_context, is_new=True)
        db.commit()
    captured = _is_contact_captured(cfg, contact) if contact else True
    return WidgetSessionOut(
        session_token=new_session.session_token,
        contact_captured=captured,
    )


# ── Visible directions for widget visitors ────────────────────────────────────
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


def update_widget_contact(
    db: Session,
    public_key: str,
    origin: str | None,
    session_token: str | None,
    data: ContactCaptureInput,
) -> None:
    """
    PATCH /public/widgets/{public_key}/session/contact

    Updates the anonymous Contact linked to this widget session with
    visitor-supplied identity data. Validates required fields per channel config.
    """
    channel = _resolve_active_web_widget(db, public_key)
    _check_origin(channel, origin)
    session = _resolve_session_or_401(db, channel, session_token)
    cfg = _get_cfg(channel)

    contact = db.get(Contact, session.contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session contact not found.",
        )

    # Validate required fields against channel config.
    errors: list[str] = []
    if cfg.get("require_name") and not data.name:
        errors.append("name is required for this widget.")
    if cfg.get("require_email") and not data.email:
        errors.append("email is required for this widget.")
    if cfg.get("require_phone") and not data.phone:
        errors.append("phone is required for this widget.")
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )

    # Apply updates — only overwrite if a value was provided.
    if data.name is not None:
        contact.name = data.name
    if data.email is not None:
        contact.email = data.email
    if data.phone is not None:
        contact.phone = data.phone

    # Reflect name on conversation.contact_name if the model has it.
    if data.name is not None:
        conv = db.get(Conversation, session.conversation_id)
        if conv and hasattr(conv, "contact_name"):
            conv.contact_name = data.name

    db.commit()


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
    cfg = _get_cfg(channel)

    # Block messages if contact capture is required but not yet fulfilled.
    if cfg.get("contact_capture_enabled"):
        contact = db.get(Contact, session.contact_id)
        if contact and not _is_contact_captured(cfg, contact):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="contact_required",
            )

    msg_data = ConversationMessageCreate(
        direction="inbound",
        sender_type="customer",
        content=data.content,
        content_type="text",
    )

    from app.services.conversation_message_service import create_message  # noqa: PLC0415

    msg = create_message(
        db=db,
        workspace_id=session.workspace_id,
        conversation_id=session.conversation_id,
        current_user_id=None,
        data=msg_data,
    )

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
