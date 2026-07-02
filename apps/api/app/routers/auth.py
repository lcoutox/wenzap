"""
First-party authentication router.

Provides signup, login, logout, /me, forgot-password, reset-password,
verify-email and resend-verification-email.
Authentication uses wenzap_session HttpOnly cookies backed by auth_sessions table.
"""

import hashlib
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.cookies import clear_auth_cookie, set_auth_cookie
from app.auth.dependencies import get_current_user
from app.auth.password import hash_password, validate_password_strength, verify_password
from app.auth.sessions import (
    create_session,
    get_session_by_token,
    revoke_all_user_sessions,
    revoke_session,
)
from app.config import settings
from app.database import get_db
from app.enums import MemberRole, MemberStatus, WorkspaceStatus
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.user import User
from app.models.user_auth_credential import UserAuthCredential
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_subscription import WorkspaceSubscription
from app.schemas.auth import (
    AuthMeOut,
    AuthUserOut,
    AuthWorkspaceOut,
    ForgotPasswordRequest,
    LoginRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyEmailRequest,
)
from app.services.email_service import get_email_service
from app.services.email_templates import verification_email_html, verification_email_text
from app.services.rate_limiter import _check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

_VERIFICATION_TOKEN_TTL_HOURS = 24
_RESEND_LIMIT = 3
_RESEND_WINDOW_SECONDS = 15 * 60  # 15 minutes


def _generate_verification_token(user_id: uuid.UUID, db: Session) -> str:
    """Generate a raw verification token, invalidate old ones, persist hash. Returns raw token."""
    # Invalidate any existing unused tokens for this user
    existing = db.scalars(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for t in existing:
        t.used_at = now  # mark as consumed so they can't be reused

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    db.add(EmailVerificationToken(
        id=uuid.uuid4(),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=now + timedelta(hours=_VERIFICATION_TOKEN_TTL_HOURS),
    ))
    return raw


def _send_verification_email(user: User, raw_token: str) -> None:
    """Build verification URL and dispatch email (fake in dev, SendGrid in prod)."""
    url = f"{settings.app_url}/verify-email?token={raw_token}"
    html = verification_email_html(url)
    text = verification_email_text(url)
    get_email_service().send(
        to=user.email,
        subject="Confirme seu e-mail no Wenzap",
        html=html,
        text=text,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unique_slug(base_email: str, db: Session) -> str:
    base = re.sub(r"[^a-z0-9]", "-", base_email.split("@")[0].lower()).strip("-") or "workspace"
    base = base[:40]
    slug, suffix = base, 1
    while db.scalar(select(Workspace).where(Workspace.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _require_starter_plan(db: Session) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.code == "starter", Plan.is_active.is_(True)))
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform configuration error: starter plan not available.",
        )
    return plan


def _provision_workspace(user: User, db: Session) -> Workspace:
    """Create default workspace + member + subscription for a new user."""
    starter = _require_starter_plan(db)
    slug = _unique_slug(user.email, db)
    name_part = user.name.split()[0] if user.name else user.email.split("@")[0]
    workspace = Workspace(
        id=uuid.uuid4(),
        name=f"Workspace de {name_part}",
        slug=slug,
        owner_user_id=user.id,
        status=WorkspaceStatus.active.value,
    )
    db.add(workspace)
    db.flush()

    db.add(WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=MemberRole.owner.value,
        status=MemberStatus.active.value,
    ))

    now = datetime.now(timezone.utc)
    db.add(WorkspaceSubscription(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        plan_id=starter.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=365),
    ))
    db.add(UsageCounter(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        period_start=now,
        period_end=now + timedelta(days=30),
    ))
    db.flush()
    return workspace


def _get_user_workspace(user: User, db: Session) -> Workspace:
    member = db.scalar(
        select(WorkspaceMember)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.status == MemberStatus.active.value,
            Workspace.status == WorkspaceStatus.active.value,
        )
        .order_by(Workspace.created_at)
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No active workspace found"
        )
    workspace = db.scalar(select(Workspace).where(Workspace.id == member.workspace_id))
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


def _build_me_response(user: User, workspace: Workspace) -> AuthMeOut:
    return AuthMeOut(
        user=AuthUserOut.model_validate(user),
        workspace=AuthWorkspaceOut.model_validate(workspace),
    )


def _get_token_from_cookie(request: Request) -> str | None:
    return request.cookies.get(settings.auth_cookie_name)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=AuthMeOut, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest, response: Response, request: Request, db: Session = Depends(get_db)
) -> AuthMeOut:
    validate_password_strength(body.password)

    existing = db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado."
        )

    name = body.name or body.email.split("@")[0]
    user = User(
        id=uuid.uuid4(),
        email=body.email,
        name=name,
        external_id=None,
        email_verified=False,
    )
    db.add(user)
    db.flush()

    db.add(UserAuthCredential(
        id=uuid.uuid4(),
        user_id=user.id,
        password_hash=hash_password(body.password),
    ))

    workspace = _provision_workspace(user, db)
    raw_token = _generate_verification_token(user.id, db)

    _, session_token = create_session(
        db,
        user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado."
        )

    db.refresh(user)
    db.refresh(workspace)
    set_auth_cookie(response, session_token)

    try:
        _send_verification_email(user, raw_token)
    except Exception:
        logger.exception("Failed to send verification email to %s", user.email)
        # Don't block signup if email delivery fails — user can resend

    logger.info("New user signed up: %s (workspace: %s)", user.id, workspace.slug)
    return _build_me_response(user, workspace)


@router.post("/login", response_model=AuthMeOut)
def login(
    body: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)
) -> AuthMeOut:
    user = db.scalar(select(User).where(User.email == body.email))
    credential = (
        db.scalar(select(UserAuthCredential).where(UserAuthCredential.user_id == user.id))
        if user
        else None
    )

    invalid = (
        user is None
        or credential is None
        or not verify_password(body.password, credential.password_hash)
    )
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )

    workspace = _get_user_workspace(user, db)
    _, token = create_session(
        db,
        user.id,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    set_auth_cookie(response, token)
    return _build_me_response(user, workspace)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, request: Request, db: Session = Depends(get_db)) -> None:
    token = _get_token_from_cookie(request)
    if token:
        revoke_session(db, token)
        db.commit()
    clear_auth_cookie(response)


@router.get("/me", response_model=AuthMeOut)
def me(request: Request, db: Session = Depends(get_db)) -> AuthMeOut:
    token = _get_token_from_cookie(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = get_session_by_token(db, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired or revoked"
        )

    db.commit()

    user = db.scalar(select(User).where(User.id == session.user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    workspace = _get_user_workspace(user, db)
    return _build_me_response(user, workspace)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(body: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict:
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    record = db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.expires_at > now,
            EmailVerificationToken.used_at.is_(None),
        )
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link de verificação inválido ou expirado.",
        )

    user = db.scalar(select(User).where(User.id == record.user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário não encontrado."
        )

    user.email_verified = True
    user.email_verified_at = now
    record.used_at = now
    db.commit()
    logger.info("Email verified for user %s", user.id)
    return {"message": "E-mail confirmado com sucesso."}


@router.post("/resend-verification-email", status_code=status.HTTP_200_OK)
def resend_verification_email(
    request: Request,
    _body: ResendVerificationRequest = ResendVerificationRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if current_user.email_verified:
        return {"message": "E-mail já verificado."}

    ip = request.client.host if request.client else "unknown"
    _check(f"resend_verify:{current_user.id}", limit=_RESEND_LIMIT, window_seconds=_RESEND_WINDOW_SECONDS)  # noqa: E501
    _check(f"resend_verify_ip:{ip}", limit=_RESEND_LIMIT, window_seconds=_RESEND_WINDOW_SECONDS)

    raw_token = _generate_verification_token(current_user.id, db)
    db.commit()

    try:
        _send_verification_email(current_user, raw_token)
    except Exception:
        logger.exception("Failed to resend verification email to %s", current_user.email)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível enviar o e-mail. Tente novamente em instantes.",
        )

    return {"message": "E-mail de verificação reenviado."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.email == body.email))
    if user is not None:
        credential = db.scalar(
            select(UserAuthCredential).where(UserAuthCredential.user_id == user.id)
        )
        if credential is not None:
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            db.add(PasswordResetToken(
                id=uuid.uuid4(),
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            ))
            db.commit()
            # Dev stub: log the reset link. Replace with SMTP when email delivery is implemented.
            logger.info(
                "[DEV] Password reset link for %s: /auth/reset-password?token=%s",
                body.email,
                raw_token,
            )

    return {"message": "Se o e-mail estiver cadastrado, você receberá um link de recuperação."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    validate_password_strength(body.new_password)

    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    reset_token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.expires_at > now,
            PasswordResetToken.used_at.is_(None),
        )
    )
    if reset_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado.",
        )

    credential = db.scalar(
        select(UserAuthCredential).where(UserAuthCredential.user_id == reset_token.user_id)
    )
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado.",
        )

    credential.password_hash = hash_password(body.new_password)
    credential.password_updated_at = now
    reset_token.used_at = now

    revoke_all_user_sessions(db, reset_token.user_id)
    db.commit()
    return {"message": "Senha redefinida com sucesso."}
