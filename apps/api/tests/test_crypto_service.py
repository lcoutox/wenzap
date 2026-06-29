"""
Tests for crypto_service — ES.1.

Covers:
- encrypt/decrypt roundtrip
- encrypted value is not the same as plaintext
- decryption with wrong key raises CredentialEncryptionError
- missing key raises CredentialEncryptionError
"""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.services.crypto_service import (
    CredentialEncryptionError,
    decrypt_secret,
    encrypt_secret,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _valid_key() -> str:
    return Fernet.generate_key().decode()


# ── Roundtrip ─────────────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    key = _valid_key()
    plain = "super-secret-token-abc123"
    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = key
        encrypted = encrypt_secret(plain)
        result = decrypt_secret(encrypted)
    assert result == plain


def test_encrypted_value_differs_from_plaintext():
    key = _valid_key()
    plain = "my-access-token"
    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = key
        encrypted = encrypt_secret(plain)
    assert encrypted != plain
    assert plain not in encrypted


def test_encrypt_produces_different_ciphertext_each_call():
    """Fernet uses random IV — same plaintext should yield different ciphertext."""
    key = _valid_key()
    plain = "same-token"
    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = key
        enc1 = encrypt_secret(plain)
        enc2 = encrypt_secret(plain)
    assert enc1 != enc2


# ── Key validation ─────────────────────────────────────────────────────────────

def test_encrypt_raises_with_missing_key():
    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = ""
        with pytest.raises(CredentialEncryptionError, match="APP_ENCRYPTION_KEY is not configured"):
            encrypt_secret("some-value")


def test_decrypt_raises_with_missing_key():
    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = ""
        with pytest.raises(CredentialEncryptionError, match="APP_ENCRYPTION_KEY is not configured"):
            decrypt_secret("some-encrypted-value")


def test_decrypt_raises_with_wrong_key():
    key1 = _valid_key()
    key2 = _valid_key()
    plain = "secret"
    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = key1
        encrypted = encrypt_secret(plain)

    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = key2
        with pytest.raises(CredentialEncryptionError, match="Failed to decrypt"):
            decrypt_secret(encrypted)


def test_encrypt_raises_with_invalid_key():
    with patch("app.services.crypto_service.settings") as mock_settings:
        mock_settings.app_encryption_key = "not-a-valid-fernet-key"
        with pytest.raises(CredentialEncryptionError, match="invalid"):
            encrypt_secret("some-value")
