"""
Tests for conversation_agent_reply_service._maybe_deliver_voice_reply —
whatsapp-voice-groq-elevenlabs-prd.md.

Best-effort, additive voice reply: only attempted when the agent has
voice_reply_enabled + elevenlabs_voice_id AND the workspace has an ElevenLabs
key configured. Never blocks or replaces the (already-sent) text reply.

Patch targets follow the local-import convention used elsewhere in this
service (e.g. catalog_media_delivery_service tests): the consuming function
does `from app.services.X import Y` INSIDE the function body, so patching
the source module attribute (not a module-level re-import) is what actually
intercepts the call.
"""

import uuid
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.workspace import Workspace
from app.services.conversation_agent_reply_service import _maybe_deliver_voice_reply
from app.services.workspace_credentials_service import set_workspace_credential

_TEST_KEY = Fernet.generate_key().decode()

_SYNTHESIZE = "app.services.elevenlabs_voice_service.synthesize_speech"
_GET_STORAGE = "app.services.storage.factory.get_storage_provider"
_DELIVER_MEDIA = "app.services.messaging.deliver_media_message"


def _make_agent(db: Session, ws_id: uuid.UUID, *, enabled: bool, voice_id: str | None) -> Agent:
    agent = Agent(workspace_id=ws_id, name="Voice Agent", status="active")
    db.add(agent)
    db.flush()
    db.add(
        AgentPromptSettings(
            agent_id=agent.id,
            voice_reply_enabled=enabled,
            elevenlabs_voice_id=voice_id,
        )
    )
    db.flush()
    return agent


def _make_agent_without_prompt_settings(db: Session, ws_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=ws_id, name="No Settings Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_conversation(db: Session, ws_id: uuid.UUID, agent: Agent) -> Conversation:
    conv = Conversation(
        workspace_id=ws_id, agent_id=agent.id, status="open", channel_type="whatsapp"
    )
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


def _messages_for(db: Session, conv_id: uuid.UUID) -> list[ConversationMessage]:
    return list(
        db.scalars(
            select(ConversationMessage).where(ConversationMessage.conversation_id == conv_id)
        )
    )


# ── Skip conditions ────────────────────────────────────────────────────────────


def test_no_prompt_settings_row_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent_without_prompt_settings(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        _maybe_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    mock_synth.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_toggle_disabled_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id, enabled=False, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        _maybe_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    mock_synth.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_missing_voice_id_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id=None)
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        _maybe_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    mock_synth.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_no_elevenlabs_credential_configured_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        _maybe_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    mock_synth.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_synthesis_failure_is_skipped(db: Session, workspace_a: Workspace, monkeypatch):
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with (
        patch(_SYNTHESIZE, return_value=None),
        patch(_DELIVER_MEDIA) as mock_deliver,
    ):
        _maybe_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    mock_deliver.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_storage_write_failure_creates_no_message(db: Session, workspace_a: Workspace, monkeypatch):
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    broken_storage = MagicMock()
    broken_storage.put_file.side_effect = Exception("disk full")

    with (
        patch(_SYNTHESIZE, return_value=b"mp3-bytes"),
        patch(_GET_STORAGE, return_value=broken_storage),
        patch(_DELIVER_MEDIA) as mock_deliver,
    ):
        _maybe_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    mock_deliver.assert_not_called()
    assert _messages_for(db, conv.id) == []


# ── Success ────────────────────────────────────────────────────────────────────


def test_success_creates_audio_message_and_delivers(
    db: Session, workspace_a: Workspace, monkeypatch
):
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    fake_storage = MagicMock()

    with (
        patch(_SYNTHESIZE, return_value=b"mp3-bytes") as mock_synth,
        patch(_GET_STORAGE, return_value=fake_storage),
        patch(_DELIVER_MEDIA) as mock_deliver,
    ):
        _maybe_deliver_voice_reply(
            db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            reply_text="Claro, o horário de funcionamento é das 9h às 18h.",
        )

    mock_synth.assert_called_once_with(
        "el-real-key", "Claro, o horário de funcionamento é das 9h às 18h.", "voice123"
    )

    messages = _messages_for(db, conv.id)
    assert len(messages) == 1
    voice_msg = messages[0]
    assert voice_msg.content_type == "audio"
    assert voice_msg.direction == "outbound"
    assert voice_msg.sender_type == "agent"
    assert voice_msg.agent_id == agent.id
    assert voice_msg.media_url is not None

    fake_storage.put_file.assert_called_once()
    stored_key, stored_bytes = fake_storage.put_file.call_args[0][:2]
    assert stored_key == voice_msg.media_url
    assert stored_bytes == b"mp3-bytes"

    mock_deliver.assert_called_once()
    args, kwargs = mock_deliver.call_args
    assert args[0] is db
    assert args[1].id == voice_msg.id
    assert args[2].id == conv.id
    assert kwargs["storage_key"] == voice_msg.media_url
    assert kwargs["mime_type"] == "audio/mpeg"


def test_delivery_failure_does_not_remove_the_message(
    db: Session, workspace_a: Workspace, monkeypatch
):
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with (
        patch(_SYNTHESIZE, return_value=b"mp3-bytes"),
        patch(_GET_STORAGE, return_value=MagicMock()),
        patch(_DELIVER_MEDIA, side_effect=Exception("evolution api down")),
    ):
        _maybe_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    messages = _messages_for(db, conv.id)
    assert len(messages) == 1
    assert messages[0].content_type == "audio"
