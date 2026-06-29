"""
Tests for POST /conversations/{id}/messages/{msg_id}/retry-delivery

Covers:
  - 404 when message does not exist
  - 422 when conversation channel_type != whatsapp
  - 422 when message is inbound (not outbound)
  - 422 when message sender_type is customer
  - 422 when delivery.status is not failed
  - 200 + re-delivery attempt when message is failed outbound/human
  - 200 + re-delivery attempt when message is failed outbound/agent
  - RBAC: viewer cannot retry
"""

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.user import User
from app.models.workspace import Workspace
from app.enums import MemberRole, MemberStatus
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client, _make_user


# ── Helpers ───────────────────────────────────────────────────────────────────


def _seed_contact(db: Session, workspace: Workspace) -> Contact:
    c = Contact(workspace_id=workspace.id, name="Retry Test Contact")
    db.add(c)
    db.flush()
    return c


def _seed_agent(db: Session, workspace: Workspace) -> Agent:
    a = Agent(workspace_id=workspace.id, name=f"RetryAgent-{uuid.uuid4().hex[:6]}")
    db.add(a)
    db.flush()
    return a


def _seed_conversation(
    db: Session,
    workspace: Workspace,
    contact: Contact,
    channel_type: str = "whatsapp",
) -> Conversation:
    conv = Conversation(
        workspace_id=workspace.id,
        contact_id=contact.id,
        status="open",
        channel_type=channel_type,
        ai_enabled=False,
    )
    db.add(conv)
    db.flush()
    return conv


def _seed_message(
    db: Session,
    workspace: Workspace,
    conversation: Conversation,
    direction: str = "outbound",
    sender_type: str = "human",
    metadata_json: dict | None = None,
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=workspace.id,
        conversation_id=conversation.id,
        direction=direction,
        sender_type=sender_type,
        content="Olá, como posso ajudar?",
        metadata_json=metadata_json,
    )
    db.add(msg)
    db.flush()
    return msg


def _failed_delivery() -> dict:
    return {
        "delivery": {
            "channel": "whatsapp",
            "provider": "meta_cloud_api",
            "status": "failed",
            "error_type": "http_error",
            "error_status": 401,
            "error_message": "Invalid OAuth access token.",
            "failed_at": "2026-06-28T10:00:00+00:00",
        }
    }


def _retry_url(conv_id, msg_id) -> str:
    return f"/conversations/{conv_id}/messages/{msg_id}/retry-delivery"


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRetryDelivery:
    def test_404_when_message_not_found(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact)
        db.commit()

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.post(_retry_url(conv.id, uuid.uuid4()))
        assert resp.status_code == 404

    def test_422_when_channel_is_not_whatsapp(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact, channel_type="internal")
        msg = _seed_message(db, workspace_a, conv, metadata_json=_failed_delivery())
        db.commit()

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.post(_retry_url(conv.id, msg.id))
        assert resp.status_code == 422
        assert "WhatsApp" in resp.json()["detail"]

    def test_422_when_message_is_inbound(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact)
        msg = _seed_message(
            db, workspace_a, conv,
            direction="inbound", sender_type="customer",
            metadata_json=_failed_delivery(),
        )
        db.commit()

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.post(_retry_url(conv.id, msg.id))
        assert resp.status_code == 422
        assert "outbound" in resp.json()["detail"]

    def test_422_when_delivery_not_failed(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact)
        sent_meta = {"delivery": {"status": "sent", "channel": "whatsapp"}}
        msg = _seed_message(db, workspace_a, conv, metadata_json=sent_meta)
        db.commit()

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.post(_retry_url(conv.id, msg.id))
        assert resp.status_code == 422
        assert "failed" in resp.json()["detail"]

    def test_422_when_delivery_is_none(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact)
        msg = _seed_message(db, workspace_a, conv, metadata_json=None)
        db.commit()

        with _make_client(db, user_a, workspace_a) as client:
            resp = client.post(_retry_url(conv.id, msg.id))
        assert resp.status_code == 422

    def test_200_calls_deliver_for_failed_human_message(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact)
        msg = _seed_message(db, workspace_a, conv, metadata_json=_failed_delivery())
        db.commit()

        with _make_client(db, user_a, workspace_a) as client:
            with patch(
                "app.services.whatsapp_outbound_service.deliver_human_message"
            ) as mock_deliver:
                resp = client.post(_retry_url(conv.id, msg.id))

        assert resp.status_code == 200
        mock_deliver.assert_called_once()
        call_args = mock_deliver.call_args
        assert str(call_args.args[1].id) == str(msg.id)

    def test_200_calls_deliver_for_failed_agent_message(
        self, db: Session, user_a: User, workspace_a: Workspace
    ):
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact)
        msg = _seed_message(
            db, workspace_a, conv,
            direction="outbound", sender_type="agent",
            metadata_json=_failed_delivery(),
        )
        db.commit()

        with _make_client(db, user_a, workspace_a) as client:
            with patch(
                "app.services.whatsapp_outbound_service.deliver_human_message"
            ) as mock_deliver:
                resp = client.post(_retry_url(conv.id, msg.id))

        assert resp.status_code == 200
        mock_deliver.assert_called_once()

    def test_viewer_cannot_retry(
        self, db: Session, workspace_a: Workspace
    ):
        viewer = _make_user(db, "viewer-retry@test.com", "Viewer")
        db.add(WorkspaceMember(
            workspace_id=workspace_a.id,
            user_id=viewer.id,
            role=MemberRole.viewer,
            status=MemberStatus.active,
        ))
        contact = _seed_contact(db, workspace_a)
        conv = _seed_conversation(db, workspace_a, contact)
        msg = _seed_message(db, workspace_a, conv, metadata_json=_failed_delivery())
        db.commit()

        with _make_client(db, viewer, workspace_a) as client:
            resp = client.post(_retry_url(conv.id, msg.id))
        assert resp.status_code == 403
