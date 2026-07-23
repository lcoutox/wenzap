"""
Tests for workspace_credentials_service — whatsapp-voice-groq-elevenlabs-prd.md.

Same encryption primitive and test pattern as test_channel_credentials_service.py
(patch app.services.crypto_service.settings.app_encryption_key), but scoped to
workspace instead of channel — no "env:"/"db:" reference indirection, keys are
always DB-stored and always customer-owned.

Covers:
- set_workspace_credential: creates, encrypts (plaintext never stored)
- set_workspace_credential: upserts on (workspace_id, provider)
- get_workspace_credential: decrypts, returns None when absent
- get_workspace_credential: returns None (not raises) on decrypt failure
- has_workspace_credential: True/False
- delete_workspace_credential: deletes, returns False when absent
- tenant isolation: a credential set for workspace A is invisible to workspace B
"""

import uuid

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.models.workspace import Workspace
from app.services.workspace_credentials_service import (
    delete_workspace_credential,
    get_workspace_credential,
    has_workspace_credential,
    set_workspace_credential,
)
from tests.conftest import _make_user, _make_workspace

_TEST_KEY = Fernet.generate_key().decode()


def _with_key(monkeypatch) -> None:
    monkeypatch.setattr("app.services.crypto_service.settings.app_encryption_key", _TEST_KEY)


def test_set_credential_encrypts_and_returns_row(db: Session, workspace_a: Workspace, monkeypatch):
    _with_key(monkeypatch)
    cred = set_workspace_credential(db, workspace_a.id, "groq", "gsk-plain-value")

    assert cred.id is not None
    assert cred.workspace_id == workspace_a.id
    assert cred.provider == "groq"
    assert cred.encrypted_value != "gsk-plain-value"
    assert "gsk-plain-value" not in cred.encrypted_value


def test_set_credential_upserts_on_workspace_and_provider(
    db: Session, workspace_a: Workspace, monkeypatch
):
    _with_key(monkeypatch)
    first = set_workspace_credential(db, workspace_a.id, "groq", "key-one")
    second = set_workspace_credential(db, workspace_a.id, "groq", "key-two")

    assert first.id == second.id
    assert get_workspace_credential(db, workspace_a.id, "groq") == "key-two"


def test_get_credential_decrypts_roundtrip(db: Session, workspace_a: Workspace, monkeypatch):
    _with_key(monkeypatch)
    set_workspace_credential(db, workspace_a.id, "elevenlabs", "el-secret-key")

    assert get_workspace_credential(db, workspace_a.id, "elevenlabs") == "el-secret-key"


def test_get_credential_returns_none_when_absent(db: Session, workspace_a: Workspace):
    assert get_workspace_credential(db, workspace_a.id, "groq") is None


def test_get_credential_returns_none_on_decrypt_failure(
    db: Session, workspace_a: Workspace, monkeypatch
):
    _with_key(monkeypatch)
    set_workspace_credential(db, workspace_a.id, "groq", "key-one")

    # Simulate a key rotation that invalidates the previously-encrypted value.
    monkeypatch.setattr(
        "app.services.crypto_service.settings.app_encryption_key",
        Fernet.generate_key().decode(),
    )
    assert get_workspace_credential(db, workspace_a.id, "groq") is None


def test_has_credential_true_and_false(db: Session, workspace_a: Workspace, monkeypatch):
    _with_key(monkeypatch)
    assert has_workspace_credential(db, workspace_a.id, "groq") is False
    set_workspace_credential(db, workspace_a.id, "groq", "key-one")
    assert has_workspace_credential(db, workspace_a.id, "groq") is True


def test_delete_credential_removes_row(db: Session, workspace_a: Workspace, monkeypatch):
    _with_key(monkeypatch)
    set_workspace_credential(db, workspace_a.id, "groq", "key-one")

    assert delete_workspace_credential(db, workspace_a.id, "groq") is True
    assert has_workspace_credential(db, workspace_a.id, "groq") is False


def test_delete_credential_returns_false_when_absent(db: Session, workspace_a: Workspace):
    assert delete_workspace_credential(db, workspace_a.id, "groq") is False


def test_credential_is_isolated_per_workspace(db: Session, workspace_a: Workspace, monkeypatch):
    _with_key(monkeypatch)
    other_owner = _make_user(db, f"u{uuid.uuid4().hex[:6]}@t.com", "Other Owner")
    workspace_b = _make_workspace(db, other_owner, f"ws-{uuid.uuid4().hex[:6]}", "WS B")

    set_workspace_credential(db, workspace_a.id, "groq", "a-secret")

    assert get_workspace_credential(db, workspace_b.id, "groq") is None
    assert has_workspace_credential(db, workspace_b.id, "groq") is False
