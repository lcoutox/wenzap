import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_workspace, get_verified_user
from app.database import get_db
from app.enums import MemberRole
from app.models.conversation_message import ConversationMessage
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.conversation import ConversationCreate, ConversationOut, ConversationUpdate
from app.schemas.conversation_message import ConversationMessageCreate, ConversationMessageOut
from app.services import conversation_message_service, conversation_service
from app.services.workspace_service import get_current_member_role

router = APIRouter(prefix="/conversations", dependencies=[Depends(get_verified_user)])

_READ_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member, MemberRole.viewer}
_WRITE_ROLES = {MemberRole.owner, MemberRole.admin, MemberRole.member}


def _require_role(
    allowed: set[MemberRole],
    db: Session,
    workspace: Workspace,
    user: User,
) -> MemberRole:
    role = get_current_member_role(db, workspace.id, user.id)
    if role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissões insuficientes.",
        )
    return role


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    status: str | None = None,
    contact_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[ConversationOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return conversation_service.list_conversations(
        db,
        current_workspace.id,
        status_filter=status,
        contact_id=contact_id,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return conversation_service.create_conversation(db, current_workspace.id, data)


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationOut:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return conversation_service.get_conversation_detail(
        db, current_workspace.id, conversation_id
    )


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: uuid.UUID,
    data: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return conversation_service.update_conversation(
        db, current_workspace.id, conversation_id, data
    )


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageOut])
def list_messages(
    conversation_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> list[ConversationMessageOut]:
    _require_role(_READ_ROLES, db, current_workspace, current_user)
    return conversation_message_service.list_messages(
        db, current_workspace.id, conversation_id, skip=skip, limit=limit
    )


@router.post("/{conversation_id}/take-over", response_model=ConversationOut)
def take_over_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return conversation_service.take_over_conversation(
        db, current_workspace.id, conversation_id, current_user.id
    )


@router.post("/{conversation_id}/return-to-ai", response_model=ConversationOut)
def return_conversation_to_ai(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return conversation_service.return_to_ai(
        db, current_workspace.id, conversation_id
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    conversation_id: uuid.UUID,
    data: ConversationMessageCreate,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationMessageOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)
    return conversation_message_service.create_message(
        db, current_workspace.id, conversation_id, current_user.id, data
    )


@router.post(
    "/{conversation_id}/messages/{message_id}/retry-delivery",
    response_model=ConversationMessageOut,
)
def retry_message_delivery(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> ConversationMessageOut:
    _require_role(_WRITE_ROLES, db, current_workspace, current_user)

    conv = conversation_service.get_conversation_or_404(
        db, current_workspace.id, conversation_id
    )
    if conv.channel_type != "whatsapp":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Reenvio é suportado apenas para conversas do WhatsApp.",
        )

    msg = db.scalar(
        select(ConversationMessage).where(
            ConversationMessage.id == message_id,
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.workspace_id == current_workspace.id,
        )
    )
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mensagem não encontrada.")

    if msg.direction != "outbound" or msg.sender_type not in {"human", "agent"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Apenas mensagens enviadas podem ser reenviadas.",
        )

    delivery = (msg.metadata_json or {}).get("delivery", {})
    if delivery.get("status") != "failed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A entrega da mensagem não está em estado de falha.",
        )

    from app.services.messaging import deliver_outbound_message  # noqa: PLC0415
    deliver_outbound_message(db, msg, conv)
    db.refresh(msg)
    return msg
