"""
Tests for GET /conversations/{id}/messages/{msg_id}/media-url —
inbox-media-playback-prd.md.

Resolves a message's stored image/audio (a storage KEY, not a browsable
URL) into a fresh presigned URL for the Inbox player.

Covers:
  - 404 when message does not exist
  - 404 when conversation belongs to another workspace
  - 422 when the message has no media (text message)
  - 422 when content_type is media-like but media_url is empty
  - 200 + presigned URL for an image message
  - 200 + presigned URL for an audio message
  - RBAC: viewer CAN read (read role), inactive/non-member cannot
"""

import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────


def _seed_contact(db: Session, workspace: Workspace) -> Contact:
    c = Contact(workspace_id=workspace.id, name="Media Test Contact")
    db.add(c)
    db.flush()
    return c


def _seed_conversation(db: Session, workspace: Workspace, contact: Contact) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        status="open",
        channel_type="whatsapp",
        ai_enabled=False,
    )
    db.add(conv)
    db.flush()
    return conv


def _seed_message(
    db: Session,
    workspace: Workspace,
    conversation: Conversation,
    *,
    content_type: str = "text",
    media_url: str | None = None,
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        direction="inbound",
        sender_type="customer",
        content="oi",
        content_type=content_type,
        media_url=media_url,
    )
    db.add(msg)
    db.flush()
    return msg


def _media_url(conv_id, msg_id) -> str:
    return f"/conversations/{conv_id}/messages/{msg_id}/media-url"


_GENERATE_PRESIGNED = "app.services.storage.factory.get_storage_provider"


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_404_when_message_not_found(db: Session, user_a: User, workspace_a: Workspace):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        resp = client.get(_media_url(conv.id, uuid.uuid4()))
    assert resp.status_code == 404


def test_404_when_conversation_from_other_workspace(
    db: Session, user_a: User, workspace_a: Workspace
):
    other_owner = _make_user(db, f"u{uuid.uuid4().hex[:6]}@t.com", "Other Owner")
    workspace_b = _make_workspace(db, other_owner, f"ws-{uuid.uuid4().hex[:6]}", "WS B")
    contact = _seed_contact(db, workspace_b)
    conv = _seed_conversation(db, workspace_b, contact)
    msg = _seed_message(db, workspace_b, conv, content_type="image", media_url="k/img.jpg")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        resp = client.get(_media_url(conv.id, msg.id))
    assert resp.status_code == 404


def test_422_when_message_has_no_media_text(db: Session, user_a: User, workspace_a: Workspace):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    msg = _seed_message(db, workspace_a, conv, content_type="text")
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        resp = client.get(_media_url(conv.id, msg.id))
    assert resp.status_code == 422


def test_422_when_content_type_media_but_no_media_url(
    db: Session, user_a: User, workspace_a: Workspace
):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    msg = _seed_message(db, workspace_a, conv, content_type="audio", media_url=None)
    db.commit()

    with _make_client(db, user_a, workspace_a) as client:
        resp = client.get(_media_url(conv.id, msg.id))
    assert resp.status_code == 422


def test_200_resolves_image_message(db: Session, user_a: User, workspace_a: Workspace):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    msg = _seed_message(
        db, workspace_a, conv, content_type="image", media_url="conversation-media/x/img.jpg"
    )
    db.commit()

    fake_storage = MagicMock()
    fake_storage.generate_presigned_url.return_value = "https://cdn.example.com/img.jpg?sig=abc"

    with _make_client(db, user_a, workspace_a) as client:
        with patch(_GENERATE_PRESIGNED, return_value=fake_storage):
            resp = client.get(_media_url(conv.id, msg.id))

    assert resp.status_code == 200
    assert resp.json() == {"url": "https://cdn.example.com/img.jpg?sig=abc"}
    fake_storage.generate_presigned_url.assert_called_once()
    assert fake_storage.generate_presigned_url.call_args.args[0] == "conversation-media/x/img.jpg"


def test_200_resolves_audio_message(db: Session, user_a: User, workspace_a: Workspace):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    msg = _seed_message(
        db, workspace_a, conv, content_type="audio", media_url="conversation-media/x/audio.ogg"
    )
    db.commit()

    fake_storage = MagicMock()
    fake_storage.generate_presigned_url.return_value = "https://cdn.example.com/audio.ogg?sig=abc"

    with _make_client(db, user_a, workspace_a) as client:
        with patch(_GENERATE_PRESIGNED, return_value=fake_storage):
            resp = client.get(_media_url(conv.id, msg.id))

    assert resp.status_code == 200
    assert resp.json() == {"url": "https://cdn.example.com/audio.ogg?sig=abc"}


def test_502_when_storage_generation_fails(db: Session, user_a: User, workspace_a: Workspace):
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    msg = _seed_message(
        db, workspace_a, conv, content_type="audio", media_url="conversation-media/x/audio.ogg"
    )
    db.commit()

    fake_storage = MagicMock()
    fake_storage.generate_presigned_url.side_effect = Exception("bucket unreachable")

    with _make_client(db, user_a, workspace_a) as client:
        with patch(_GENERATE_PRESIGNED, return_value=fake_storage):
            resp = client.get(_media_url(conv.id, msg.id))

    assert resp.status_code == 502


def test_viewer_can_read_media_url(db: Session, workspace_a: Workspace):
    viewer = _make_user(db, f"viewer-{uuid.uuid4().hex[:6]}@test.com", "Viewer")
    db.add(WorkspaceMember(
        workspace_id=workspace_a.id,
        user_id=viewer.id,
        role=MemberRole.viewer,
        status=MemberStatus.active,
    ))
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    msg = _seed_message(
        db, workspace_a, conv, content_type="image", media_url="conversation-media/x/img.jpg"
    )
    db.commit()

    fake_storage = MagicMock()
    fake_storage.generate_presigned_url.return_value = "https://cdn.example.com/img.jpg"

    with _make_client(db, viewer, workspace_a) as client:
        with patch(_GENERATE_PRESIGNED, return_value=fake_storage):
            resp = client.get(_media_url(conv.id, msg.id))
    assert resp.status_code == 200


def test_non_member_cannot_read_media_url(db: Session, workspace_a: Workspace):
    outsider = _make_user(db, f"outsider-{uuid.uuid4().hex[:6]}@test.com", "Outsider")
    contact = _seed_contact(db, workspace_a)
    conv = _seed_conversation(db, workspace_a, contact)
    msg = _seed_message(
        db, workspace_a, conv, content_type="image", media_url="conversation-media/x/img.jpg"
    )
    db.commit()

    with _make_client(db, outsider, workspace_a) as client:
        resp = client.get(_media_url(conv.id, msg.id))
    assert resp.status_code == 403
