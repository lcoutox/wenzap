import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.auth_session import AuthSession


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(
    db: Session,
    user_id: uuid.UUID,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[AuthSession, str]:
    token = secrets.token_urlsafe(32)
    token_hash = hash_session_token(token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.auth_session_ttl_days)

    session = AuthSession(
        id=uuid.uuid4(),
        user_id=user_id,
        session_token_hash=token_hash,
        expires_at=expires_at,
        last_seen_at=now,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    db.flush()
    return session, token


def get_session_by_token(db: Session, token: str) -> AuthSession | None:
    token_hash = hash_session_token(token)
    now = datetime.now(timezone.utc)
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.session_token_hash == token_hash,
            AuthSession.expires_at > now,
            AuthSession.revoked_at.is_(None),
        )
    )
    if session is not None:
        session.last_seen_at = now
        db.flush()
    return session


def revoke_session(db: Session, token: str) -> None:
    token_hash = hash_session_token(token)
    session = db.scalar(
        select(AuthSession).where(AuthSession.session_token_hash == token_hash)
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.flush()


def revoke_all_user_sessions(db: Session, user_id: uuid.UUID) -> None:
    sessions = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for s in sessions:
        s.revoked_at = now
    if sessions:
        db.flush()
