"""
Channel Credentials Service — ES.1.

Manages encrypted credentials for channel integrations.

Responsibilities:
- Store credentials encrypted in channel_credentials table.
- Resolve access tokens from either env: or db: references.
- Never log or return plaintext token values.

Token reference formats supported by resolve_channel_secret:
  "env:VAR_NAME"     → read os.environ["VAR_NAME"]
  "db:<uuid>"        → lookup ChannelCredential, validate ownership, decrypt
"""

import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel import Channel
from app.models.channel_credential import ChannelCredential
from app.services.crypto_service import CredentialEncryptionError, decrypt_secret, encrypt_secret

logger = logging.getLogger(__name__)


def create_or_update_channel_credential(
    db: Session,
    workspace_id: uuid.UUID,
    channel_id: uuid.UUID,
    provider: str,
    credential_type: str,
    plain_value: str,
    obtained_via: str,
    expires_at: datetime | None = None,
    metadata_json: dict | None = None,
) -> ChannelCredential:
    """
    Create or update the credential for a channel/provider/type combination.

    Uses upsert logic: if a credential with the same (channel_id, provider,
    credential_type) already exists, it is updated in-place (encrypted_value,
    expires_at, metadata_json, updated_at). Otherwise a new row is created.

    The plain_value is encrypted before storage and never persisted as-is.
    """
    encrypted = encrypt_secret(plain_value)

    existing = db.scalar(
        select(ChannelCredential).where(
            ChannelCredential.channel_id == channel_id,
            ChannelCredential.provider == provider,
            ChannelCredential.credential_type == credential_type,
        )
    )

    if existing is not None:
        existing.encrypted_value = encrypted
        existing.expires_at = expires_at
        existing.metadata_json = metadata_json
        existing.obtained_via = obtained_via
        existing.updated_at = datetime.now(timezone.utc)
        db.flush()
        logger.info(
            "channel_credential updated channel_id=%s provider=%s type=%s",
            channel_id,
            provider,
            credential_type,
        )
        return existing

    cred = ChannelCredential(
        workspace_id=workspace_id,
        channel_id=channel_id,
        provider=provider,
        credential_type=credential_type,
        encrypted_value=encrypted,
        metadata_json=metadata_json,
        expires_at=expires_at,
        obtained_via=obtained_via,
    )
    db.add(cred)
    db.flush()
    logger.info(
        "channel_credential created channel_id=%s provider=%s type=%s",
        channel_id,
        provider,
        credential_type,
    )
    return cred


def get_channel_credential_by_id(
    db: Session,
    credential_id: uuid.UUID,
) -> ChannelCredential | None:
    """Return a ChannelCredential by primary key, or None if not found."""
    return db.get(ChannelCredential, credential_id)


def resolve_channel_secret(
    db: Session,
    channel: Channel,
    ref: str,
) -> str | None:
    """
    Resolve a token reference string to the plaintext secret.

    Supported formats:
      "env:VAR_NAME"  — reads the named environment variable
      "db:<uuid>"     — decrypts the ChannelCredential with that ID,
                        after validating it belongs to this channel/workspace

    Returns None if:
      - the ref is empty or in an unknown format
      - the env var is not set
      - the db record does not exist or belongs to another channel/workspace

    Raises CredentialEncryptionError if decryption fails (wrong key, corrupted data).
    Never logs the resolved plaintext value.
    """
    if not ref:
        return None

    if ref.startswith("env:"):
        var_name = ref.removeprefix("env:")
        value = os.environ.get(var_name)
        if not value:
            logger.warning(
                "resolve_channel_secret env var not set ref=%s channel_id=%s",
                ref,
                channel.id,
            )
            return None
        return value

    if ref.startswith("db:"):
        raw_id = ref.removeprefix("db:")
        try:
            cred_id = uuid.UUID(raw_id)
        except ValueError:
            logger.warning(
                "resolve_channel_secret invalid db: ref format ref=%s channel_id=%s",
                ref,
                channel.id,
            )
            return None

        cred = db.get(ChannelCredential, cred_id)
        if cred is None:
            logger.warning(
                "resolve_channel_secret credential not found cred_id=%s channel_id=%s",
                cred_id,
                channel.id,
            )
            return None

        # Ownership check — never resolve a credential from a different channel or workspace.
        if cred.channel_id != channel.id or cred.workspace_id != channel.workspace_id:
            logger.warning(
                "resolve_channel_secret ownership mismatch cred_id=%s channel_id=%s",
                cred_id,
                channel.id,
            )
            return None

        try:
            return decrypt_secret(cred.encrypted_value)
        except CredentialEncryptionError:
            logger.exception(
                "resolve_channel_secret decrypt failed cred_id=%s channel_id=%s",
                cred_id,
                channel.id,
            )
            return None

    logger.warning(
        "resolve_channel_secret unknown ref format ref_prefix=%s channel_id=%s",
        ref[:10],
        channel.id,
    )
    return None
