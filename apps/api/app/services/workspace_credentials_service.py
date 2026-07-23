"""
Workspace Credentials Service — whatsapp-voice-groq-elevenlabs-prd.md.

Manages encrypted, customer-supplied API keys for third-party services
(Groq, ElevenLabs) scoped to a workspace — not a channel. Same encryption
primitive as channel_credentials_service.py (Fernet via crypto_service.py),
but with no "env:"/"db:" reference indirection: these keys are always
customer-owned and always stored in the DB, so callers resolve them
directly by (workspace_id, provider).

Never logs or returns plaintext values.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace_credential import WorkspaceCredential
from app.services.crypto_service import CredentialEncryptionError, decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {"groq", "elevenlabs"}


def set_workspace_credential(
    db: Session,
    workspace_id: uuid.UUID,
    provider: str,
    plain_value: str,
) -> WorkspaceCredential:
    """
    Create or update the customer-supplied key for (workspace_id, provider).

    The plain_value is encrypted before storage and never persisted as-is.
    """
    encrypted = encrypt_secret(plain_value)

    existing = db.scalar(
        select(WorkspaceCredential).where(
            WorkspaceCredential.workspace_id == workspace_id,
            WorkspaceCredential.provider == provider,
        )
    )

    if existing is not None:
        existing.encrypted_value = encrypted
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        logger.info(
            "workspace_credential updated workspace_id=%s provider=%s", workspace_id, provider
        )
        return existing

    cred = WorkspaceCredential(
        workspace_id=workspace_id,
        provider=provider,
        encrypted_value=encrypted,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    logger.info("workspace_credential created workspace_id=%s provider=%s", workspace_id, provider)
    return cred


def get_workspace_credential(
    db: Session,
    workspace_id: uuid.UUID,
    provider: str,
) -> str | None:
    """Return the decrypted key for (workspace_id, provider), or None if not configured."""
    cred = db.scalar(
        select(WorkspaceCredential).where(
            WorkspaceCredential.workspace_id == workspace_id,
            WorkspaceCredential.provider == provider,
        )
    )
    if cred is None:
        return None
    try:
        return decrypt_secret(cred.encrypted_value)
    except CredentialEncryptionError:
        logger.exception(
            "workspace_credential decrypt failed workspace_id=%s provider=%s",
            workspace_id,
            provider,
        )
        return None


def has_workspace_credential(db: Session, workspace_id: uuid.UUID, provider: str) -> bool:
    return (
        db.scalar(
            select(WorkspaceCredential.id).where(
                WorkspaceCredential.workspace_id == workspace_id,
                WorkspaceCredential.provider == provider,
            )
        )
        is not None
    )


def delete_workspace_credential(db: Session, workspace_id: uuid.UUID, provider: str) -> bool:
    """Delete the credential if it exists. Returns True if a row was deleted."""
    cred = db.scalar(
        select(WorkspaceCredential).where(
            WorkspaceCredential.workspace_id == workspace_id,
            WorkspaceCredential.provider == provider,
        )
    )
    if cred is None:
        return False
    db.delete(cred)
    db.commit()
    return True
