from datetime import timedelta

from fastapi import Response

from app.config import settings

_COOKIE_MAX_AGE = int(timedelta(days=settings.auth_session_ttl_days).total_seconds())


def _domain() -> str | None:
    return settings.auth_cookie_domain or None


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        path="/",
        domain=_domain(),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        domain=_domain(),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )
