"""
Symmetric encryption/decryption for sensitive channel credentials.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` library.
The key is read from settings.app_encryption_key (env: APP_ENCRYPTION_KEY).

Rules:
- Never log plaintext values.
- Never return the key in any response.
- Raise CredentialEncryptionError with a clear message if the key is absent or invalid.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)


class CredentialEncryptionError(Exception):
    """Raised when encryption or decryption fails due to configuration or data issues."""


def _get_fernet() -> Fernet:
    key = settings.app_encryption_key
    if not key:
        raise CredentialEncryptionError(
            "APP_ENCRYPTION_KEY is not configured. "
            "Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""  # noqa: E501
        )
    try:
        return Fernet(key.encode())
    except (ValueError, Exception) as exc:
        raise CredentialEncryptionError(
            "APP_ENCRYPTION_KEY is invalid. Ensure it is a valid Fernet key (base64, 32 bytes)."
        ) from exc


def encrypt_secret(value: str) -> str:
    """Encrypt a plaintext secret. Returns an opaque Fernet token string."""
    f = _get_fernet()
    return f.encrypt(value.encode()).decode()


def decrypt_secret(encrypted_value: str) -> str:
    """Decrypt a Fernet-encrypted secret. Raises CredentialEncryptionError on failure."""
    f = _get_fernet()
    try:
        return f.decrypt(encrypted_value.encode()).decode()
    except InvalidToken as exc:
        raise CredentialEncryptionError(
            "Failed to decrypt credential: invalid token or wrong key."
        ) from exc
