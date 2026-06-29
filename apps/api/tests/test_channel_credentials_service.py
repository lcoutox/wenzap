"""
Tests for channel_credentials_service — ES.1.

Covers:
- create_or_update: creates credential, encrypts token (plaintext not stored)
- create_or_update: updates existing credential (upsert)
- get_channel_credential_by_id: returns credential or None
- resolve_channel_secret: env: prefix resolves from environment
- resolve_channel_secret: db: prefix resolves and decrypts
- resolve_channel_secret: db: credential from wrong channel returns None
- resolve_channel_secret: db: credential from wrong workspace returns None
- resolve_channel_secret: db: non-existent id returns None
- resolve_channel_secret: unknown format returns None
"""

import uuid
from unittest.mock import patch

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.workspace import Workspace
from app.services.channel_credentials_service import (
    create_or_update_channel_credential,
    get_channel_credential_by_id,
    resolve_channel_secret,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

_TEST_KEY = Fernet.generate_key().decode()
_PATCH_KEY = patch("app.services.crypto_service.settings", **{"app_encryption_key": _TEST_KEY})


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_channel(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="WA Channel",
        public_key=str(uuid.uuid4()),
        status="active",
        config_json={"provider": "meta_cloud_api", "waba_id": "123", "phone_number_id": "456"},
    )
    db.add(ch)
    db.flush()
    return ch


# ── create_or_update_channel_credential ───────────────────────────────────────

def test_create_credential_encrypts_token(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)

    with patch("app.services.channel_credentials_service.encrypt_secret", wraps=_patched_encrypt):
        with patch("app.services.crypto_service.settings") as ms:
            ms.app_encryption_key = _TEST_KEY
            cred = create_or_update_channel_credential(
                db,
                workspace_id=workspace_a.id,
                channel_id=channel.id,
                provider="meta_cloud_api",
                credential_type="whatsapp_user_access_token",
                plain_value="my-plain-token",
                obtained_via="test",
            )

    assert cred.id is not None
    assert cred.channel_id == channel.id
    assert cred.workspace_id == workspace_a.id
    assert cred.provider == "meta_cloud_api"
    assert cred.credential_type == "whatsapp_user_access_token"
    assert cred.obtained_via == "test"
    # Plaintext must NOT be stored
    assert cred.encrypted_value != "my-plain-token"
    assert "my-plain-token" not in cred.encrypted_value


def _patched_encrypt(value: str) -> str:
    from app.services.crypto_service import encrypt_secret
    return encrypt_secret(value)


def test_create_or_update_updates_existing(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)

    with patch("app.services.crypto_service.settings") as ms:
        ms.app_encryption_key = _TEST_KEY
        cred1 = create_or_update_channel_credential(
            db,
            workspace_id=workspace_a.id,
            channel_id=channel.id,
            provider="meta_cloud_api",
            credential_type="whatsapp_user_access_token",
            plain_value="token-v1",
            obtained_via="test",
        )
        cred2 = create_or_update_channel_credential(
            db,
            workspace_id=workspace_a.id,
            channel_id=channel.id,
            provider="meta_cloud_api",
            credential_type="whatsapp_user_access_token",
            plain_value="token-v2",
            obtained_via="embedded_signup",
        )

    # Must be the same row (upsert)
    assert cred1.id == cred2.id
    assert cred2.obtained_via == "embedded_signup"
    # Value must have been updated
    with patch("app.services.crypto_service.settings") as ms:
        ms.app_encryption_key = _TEST_KEY
        from app.services.crypto_service import decrypt_secret
        assert decrypt_secret(cred2.encrypted_value) == "token-v2"


def test_get_channel_credential_by_id_returns_credential(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)

    with patch("app.services.crypto_service.settings") as ms:
        ms.app_encryption_key = _TEST_KEY
        cred = create_or_update_channel_credential(
            db,
            workspace_id=workspace_a.id,
            channel_id=channel.id,
            provider="meta_cloud_api",
            credential_type="whatsapp_user_access_token",
            plain_value="token-abc",
            obtained_via="test",
        )

    fetched = get_channel_credential_by_id(db, cred.id)
    assert fetched is not None
    assert fetched.id == cred.id


def test_get_channel_credential_by_id_returns_none_for_missing(db: Session):
    result = get_channel_credential_by_id(db, uuid.uuid4())
    assert result is None


# ── resolve_channel_secret ────────────────────────────────────────────────────

def test_resolve_env_reads_environment(db: Session, workspace_a: Workspace, monkeypatch):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)
    monkeypatch.setenv("TEST_WA_TOKEN", "env-token-value")

    result = resolve_channel_secret(db, channel, "env:TEST_WA_TOKEN")
    assert result == "env-token-value"


def test_resolve_env_returns_none_when_var_missing(  # noqa: E501
    db: Session, workspace_a: Workspace, monkeypatch
):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)
    monkeypatch.delenv("TEST_WA_TOKEN_MISSING", raising=False)

    result = resolve_channel_secret(db, channel, "env:TEST_WA_TOKEN_MISSING")
    assert result is None


def test_resolve_db_decrypts_token(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)

    with patch("app.services.crypto_service.settings") as ms:
        ms.app_encryption_key = _TEST_KEY
        cred = create_or_update_channel_credential(
            db,
            workspace_id=workspace_a.id,
            channel_id=channel.id,
            provider="meta_cloud_api",
            credential_type="whatsapp_user_access_token",
            plain_value="my-secret-token",
            obtained_via="test",
        )

        result = resolve_channel_secret(db, channel, f"db:{cred.id}")

    assert result == "my-secret-token"


def test_resolve_db_wrong_channel_returns_none(db: Session, workspace_a: Workspace):
    """Credential belongs to channel A; resolving via channel B must return None."""
    agent = _make_agent(db, workspace_a.id)
    channel_a = _make_channel(db, workspace_a.id, agent.id)
    channel_b = _make_channel(db, workspace_a.id, agent.id)

    with patch("app.services.crypto_service.settings") as ms:
        ms.app_encryption_key = _TEST_KEY
        cred = create_or_update_channel_credential(
            db,
            workspace_id=workspace_a.id,
            channel_id=channel_a.id,
            provider="meta_cloud_api",
            credential_type="whatsapp_user_access_token",
            plain_value="channel-a-token",
            obtained_via="test",
        )

        result = resolve_channel_secret(db, channel_b, f"db:{cred.id}")

    assert result is None


def test_resolve_db_wrong_workspace_returns_none(
    db: Session, workspace_a: Workspace, workspace_b: Workspace
):
    """Credential belongs to workspace A; channel_b from workspace B must not resolve it."""
    agent_a = _make_agent(db, workspace_a.id)
    agent_b = _make_agent(db, workspace_b.id)
    channel_a = _make_channel(db, workspace_a.id, agent_a.id)
    channel_b = _make_channel(db, workspace_b.id, agent_b.id)

    with patch("app.services.crypto_service.settings") as ms:
        ms.app_encryption_key = _TEST_KEY
        cred = create_or_update_channel_credential(
            db,
            workspace_id=workspace_a.id,
            channel_id=channel_a.id,
            provider="meta_cloud_api",
            credential_type="whatsapp_user_access_token",
            plain_value="ws-a-token",
            obtained_via="test",
        )

        result = resolve_channel_secret(db, channel_b, f"db:{cred.id}")

    assert result is None


def test_resolve_db_nonexistent_id_returns_none(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)

    result = resolve_channel_secret(db, channel, f"db:{uuid.uuid4()}")
    assert result is None


def test_resolve_unknown_format_returns_none(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)

    result = resolve_channel_secret(db, channel, "unknown:something")
    assert result is None


def test_resolve_empty_ref_returns_none(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)

    result = resolve_channel_secret(db, channel, "")
    assert result is None
