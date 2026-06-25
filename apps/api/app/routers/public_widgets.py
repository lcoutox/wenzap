"""
Public widget router — no Clerk authentication required.

These endpoints are called by the visitor's browser (the embedded widget).
Workspace and agent are resolved internally from the public_key.
The visitor never sends workspace_id or agent_id.
"""

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.public_widget import (
    ContactCaptureInput,
    PublicWidgetConfigOut,
    PublicWidgetMessageCreate,
    PublicWidgetMessageOut,
    WidgetSessionCreate,
    WidgetSessionOut,
)
from app.services import public_widget_service
from app.services.rate_limiter import check_message_rate, check_session_rate

router = APIRouter(prefix="/public/widgets")


def _get_origin(request: Request) -> str | None:
    return request.headers.get("origin")


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/{public_key}/config", response_model=PublicWidgetConfigOut)
def get_widget_config(
    public_key: str,
    request: Request,
    db: Session = Depends(get_db),
) -> PublicWidgetConfigOut:
    origin = _get_origin(request)
    return public_widget_service.get_public_widget_config(db, public_key, origin)


@router.post("/{public_key}/sessions", response_model=WidgetSessionOut)
def create_or_resume_session(
    public_key: str,
    data: WidgetSessionCreate,
    request: Request,
    db: Session = Depends(get_db),
) -> WidgetSessionOut:
    check_session_rate(_get_client_ip(request))
    origin = _get_origin(request)
    return public_widget_service.create_or_resume_widget_session(
        db, public_key, origin, data.session_token, data.page_context
    )


@router.patch(
    "/{public_key}/session/contact",
    status_code=status.HTTP_204_NO_CONTENT,
)
def update_contact(
    public_key: str,
    data: ContactCaptureInput,
    request: Request,
    x_session_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    origin = _get_origin(request)
    public_widget_service.update_widget_contact(
        db, public_key, origin, x_session_token, data
    )


@router.post(
    "/{public_key}/messages",
    response_model=PublicWidgetMessageOut,
    status_code=201,
)
def send_message(
    public_key: str,
    data: PublicWidgetMessageCreate,
    request: Request,
    x_session_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> PublicWidgetMessageOut:
    if x_session_token:
        check_message_rate(x_session_token)
    origin = _get_origin(request)
    return public_widget_service.send_widget_message(
        db, public_key, origin, x_session_token, data
    )


@router.get("/{public_key}/messages", response_model=list[PublicWidgetMessageOut])
def list_messages(
    public_key: str,
    request: Request,
    limit: int = 50,
    x_session_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[PublicWidgetMessageOut]:
    origin = _get_origin(request)
    return public_widget_service.list_widget_messages(
        db, public_key, origin, x_session_token, limit=limit
    )
