"""
Tests for conversation_agent_reply_service._try_deliver_voice_reply and
_deliver_whatsapp_reply — whatsapp-voice-groq-elevenlabs-prd.md.

Voice-first when the trigger was itself a voice note and synthesis succeeds
(mirrors how a person replies to a voice note with a voice note, not a voice
note plus a wall of text) — falls back to text on any missing precondition
or failure, so the customer is never left without a reply.

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
from app.services.conversation_agent_reply_service import (
    _deliver_whatsapp_reply,
    _try_deliver_voice_reply,
)
from app.services.conversation_context_builder import ConversationContext
from app.services.workspace_credentials_service import set_workspace_credential

_TEST_KEY = Fernet.generate_key().decode()

_SYNTHESIZE = "app.services.elevenlabs_voice_service.synthesize_speech"
_GET_STORAGE = "app.services.storage.factory.get_storage_provider"
_DELIVER_MEDIA = "app.services.messaging.deliver_media_message"
_DELIVER_OUTBOUND = "app.services.messaging.deliver_outbound_message"


def _fake_media_success(db, message, conversation, *, storage_key, mime_type, caption=None):
    existing = message.metadata_json or {}
    message.metadata_json = {**existing, "delivery": {"status": "sent", "wamid": "wamid.audio"}}
    db.commit()


def _fake_media_failure(db, message, conversation, *, storage_key, mime_type, caption=None):
    existing = message.metadata_json or {}
    message.metadata_json = {**existing, "delivery": {"status": "failed", "error": "down"}}
    db.commit()


def _fake_text_success(db, message, conversation):
    existing = message.metadata_json or {}
    message.metadata_json = {**existing, "delivery": {"status": "sent", "wamid": "wamid.text"}}
    db.commit()


def _make_agent(
    db: Session, ws_id: uuid.UUID, *, enabled: bool, voice_id: str | None
) -> Agent:
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


def _make_response_msg(
    db: Session, ws_id: uuid.UUID, conv: Conversation, agent: Agent
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=ws_id,
        conversation_id=conv.id,
        direction="outbound",
        sender_type="agent",
        agent_id=agent.id,
        content="Claro, o horário de funcionamento é das 9h às 18h.",
        content_type="text",
    )
    db.add(msg)
    db.flush()
    db.refresh(msg)
    return msg


def _make_trigger(
    db: Session, ws_id: uuid.UUID, conv: Conversation, *, content_type: str
) -> ConversationMessage:
    msg = ConversationMessage(
        workspace_id=ws_id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content="oi" if content_type == "text" else "",
        content_type=content_type,
    )
    db.add(msg)
    db.flush()
    db.refresh(msg)
    return msg


def _messages_for(db: Session, conv_id: uuid.UUID) -> list[ConversationMessage]:
    return list(
        db.scalars(
            select(ConversationMessage).where(ConversationMessage.conversation_id == conv_id)
        )
    )


def _empty_ctx() -> ConversationContext:
    return ConversationContext(
        system_prompt="",
        conversation_history="",
        reply_instruction="",
        catalog_retrieval_attempted=False,
    )


# ── _try_deliver_voice_reply: skip conditions ───────────────────────────────────


def test_no_prompt_settings_row_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent_without_prompt_settings(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False
    mock_synth.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_toggle_disabled_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id, enabled=False, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False
    mock_synth.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_missing_voice_id_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id=None)
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False
    mock_synth.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_no_elevenlabs_credential_configured_is_skipped(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with patch(_SYNTHESIZE) as mock_synth:
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False
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
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False
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
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False
    mock_deliver.assert_not_called()
    assert _messages_for(db, conv.id) == []


def test_delivery_failure_returns_false_but_keeps_the_message(
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
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False
    messages = _messages_for(db, conv.id)
    assert len(messages) == 1
    assert messages[0].content_type == "audio"


def test_provider_recorded_failed_status_returns_false(
    db: Session, workspace_a: Workspace, monkeypatch
):
    """deliver_media_message can "succeed" (no exception) but still record a
    failed delivery on the message — the provider owns that outcome. Must
    also count as False so the caller falls back to text."""
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with (
        patch(_SYNTHESIZE, return_value=b"mp3-bytes"),
        patch(_GET_STORAGE, return_value=MagicMock()),
        patch(_DELIVER_MEDIA, side_effect=_fake_media_failure),
    ):
        result = _try_deliver_voice_reply(
            db, workspace_id=workspace_a.id, conversation=conv, agent=agent, reply_text="Oi!"
        )

    assert result is False


# ── _try_deliver_voice_reply: success ───────────────────────────────────────────


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
        patch(_DELIVER_MEDIA, side_effect=_fake_media_success) as mock_deliver,
    ):
        result = _try_deliver_voice_reply(
            db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            reply_text="Claro, o horário de funcionamento é das 9h às 18h.",
        )

    assert result is True
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


def test_synthesis_uses_normalized_text_but_message_keeps_original(
    db: Session, workspace_a: Workspace, monkeypatch
):
    """
    Numbers/currency must be normalized for pronunciation before hitting
    ElevenLabs, but the persisted ConversationMessage.content (used for the
    Inbox transcript) must stay in the original, human-readable form.
    """
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)

    with (
        patch(_SYNTHESIZE, return_value=b"mp3-bytes") as mock_synth,
        patch(_GET_STORAGE, return_value=MagicMock()),
        patch(_DELIVER_MEDIA, side_effect=_fake_media_success),
    ):
        _try_deliver_voice_reply(
            db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            reply_text="O valor do imóvel é R$ 564.144,00.",
        )

    mock_synth.assert_called_once_with(
        "el-real-key",
        "O valor do imóvel é quinhentos e sessenta e quatro mil, cento e "
        "quarenta e quatro reais.",
        "voice123",
    )

    voice_msg = _messages_for(db, conv.id)[0]
    assert voice_msg.content == "O valor do imóvel é R$ 564.144,00."


# ── _deliver_whatsapp_reply: voice-first orchestration ──────────────────────────


def test_audio_trigger_with_voice_success_skips_text_delivery(
    db: Session, workspace_a: Workspace, monkeypatch
):
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)
    trigger = _make_trigger(db, workspace_a.id, conv, content_type="audio")
    response_msg = _make_response_msg(db, workspace_a.id, conv, agent)

    with (
        patch(_SYNTHESIZE, return_value=b"mp3-bytes"),
        patch(_GET_STORAGE, return_value=MagicMock()),
        patch(_DELIVER_MEDIA, side_effect=_fake_media_success),
        patch(_DELIVER_OUTBOUND) as mock_deliver_text,
    ):
        _deliver_whatsapp_reply(
            db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            response_msg=response_msg,
            trigger_message=trigger,
            reply_content=response_msg.content,
            ctx=_empty_ctx(),
        )

    mock_deliver_text.assert_not_called()
    assert response_msg.metadata_json["delivery"] == {
        "status": "skipped",
        "reason": "voice_reply_sent",
    }
    # One outbound audio reply created (in addition to the inbound audio trigger).
    messages = _messages_for(db, conv.id)
    outbound_audio = [
        m for m in messages if m.content_type == "audio" and m.direction == "outbound"
    ]
    assert len(outbound_audio) == 1


def test_audio_trigger_with_voice_failure_falls_back_to_text(
    db: Session, workspace_a: Workspace
):
    agent = _make_agent(db, workspace_a.id, enabled=False, voice_id=None)
    conv = _make_conversation(db, workspace_a.id, agent)
    trigger = _make_trigger(db, workspace_a.id, conv, content_type="audio")
    response_msg = _make_response_msg(db, workspace_a.id, conv, agent)

    with patch(_DELIVER_OUTBOUND, side_effect=_fake_text_success) as mock_deliver_text:
        _deliver_whatsapp_reply(
            db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            response_msg=response_msg,
            trigger_message=trigger,
            reply_content=response_msg.content,
            ctx=_empty_ctx(),
        )

    mock_deliver_text.assert_called_once()
    assert response_msg.metadata_json["delivery"]["status"] == "sent"


def test_text_trigger_never_attempts_voice(db: Session, workspace_a: Workspace, monkeypatch):
    """Voice-reply eligibility is irrelevant when the customer wrote text —
    only a voice-triggered turn gets a voice reply."""
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-real-key")
    agent = _make_agent(db, workspace_a.id, enabled=True, voice_id="voice123")
    conv = _make_conversation(db, workspace_a.id, agent)
    trigger = _make_trigger(db, workspace_a.id, conv, content_type="text")
    response_msg = _make_response_msg(db, workspace_a.id, conv, agent)

    with (
        patch(_SYNTHESIZE) as mock_synth,
        patch(_DELIVER_OUTBOUND, side_effect=_fake_text_success) as mock_deliver_text,
    ):
        _deliver_whatsapp_reply(
            db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            response_msg=response_msg,
            trigger_message=trigger,
            reply_content=response_msg.content,
            ctx=_empty_ctx(),
        )

    mock_synth.assert_not_called()
    mock_deliver_text.assert_called_once()
    assert response_msg.metadata_json["delivery"]["status"] == "sent"
