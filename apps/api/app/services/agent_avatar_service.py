"""
Agent avatar upload/delete service — Phase Agent UX.2.

Handles the lifecycle of agent avatar images:
  POST  → validate, upload to storage, persist metadata in agents table
  DELETE → remove from storage, clear metadata

Storage key pattern:
  workspaces/{workspace_id}/agents/{agent_id}/avatar/{uuid}-{safe_filename}

Accepted MIME types: image/jpeg, image/png, image/webp
Size limit: 5 MB
"""

import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.services.storage.base import StorageError, StorageProvider
from app.services.storage.factory import get_storage_provider

# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

_ALLOWED_MIMES: dict[str, bytes] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png":  b"\x89PNG",
    "image/webp": b"RIFF",
}

_WEBP_MARKER = b"WEBP"
_SAFE_CHAR_RE = re.compile(r"[^\w.\-]")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_filename(filename: str) -> str:
    import os
    name = os.path.basename(filename)
    name = _SAFE_CHAR_RE.sub("_", name)
    name = name.lstrip(".")[:80]
    return name or "avatar"


def _validate_image(data: bytes, content_type: str | None) -> str:
    """
    Validate image data and return normalised MIME type.

    Raises HTTPException 400 on invalid type, 413 on size exceeded.
    """
    if len(data) > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Avatar must be at most {_MAX_SIZE_BYTES // (1024 * 1024)} MB.",
        )

    normalised = (content_type or "").split(";")[0].strip().lower()

    # Detect by magic bytes first
    for mime, magic in _ALLOWED_MIMES.items():
        if data[:len(magic)] == magic:
            # Extra check: WebP must also have "WEBP" at bytes 8–11
            if mime == "image/webp" and data[8:12] != _WEBP_MARKER:
                continue
            return mime

    # If magic doesn't match but a valid MIME was declared, reject
    if normalised in _ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File declared as {normalised!r} but content does not match. "
                "Accepted: JPEG, PNG, WebP."
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Avatar must be a JPEG, PNG, or WebP image.",
    )


def _resolve_storage(storage: StorageProvider | None) -> StorageProvider:
    try:
        return storage or get_storage_provider()
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Storage não configurado para upload de avatar. ({exc})",
        ) from exc


def _delete_old_avatar(agent: Agent, storage: StorageProvider) -> None:
    """Best-effort deletion of previous avatar. Does not raise on failure."""
    if agent.avatar_file_key:
        try:
            storage.delete_file(agent.avatar_file_key)
        except StorageError:
            pass  # Non-fatal: old file may already be gone


# ── Public API ────────────────────────────────────────────────────────────────

def upload_avatar(
    db: Session,
    agent: Agent,
    file_data: bytes,
    filename: str,
    content_type: str | None,
    storage: StorageProvider | None = None,
) -> Agent:
    """
    Upload an avatar image for *agent*.

    Validates type/size, stores the file, and persists metadata on the agent row.
    Returns the updated Agent ORM object (not yet committed by caller).
    """
    resolved = _resolve_storage(storage)
    mime = _validate_image(file_data, content_type)

    safe_name = _safe_filename(filename)
    file_key = (
        f"workspaces/{agent.workspace_id}/agents/{agent.id}"
        f"/avatar/{uuid.uuid4()}-{safe_name}"
    )

    # Remove previous avatar from storage (best-effort)
    _delete_old_avatar(agent, resolved)

    try:
        resolved.put_file(file_key, file_data, content_type=mime)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao salvar avatar no storage: {exc}",
        ) from exc

    agent.avatar_file_key = file_key
    agent.avatar_mime_type = mime
    agent.avatar_size_bytes = len(file_data)
    agent.avatar_updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(agent)
    return agent


def delete_avatar(
    db: Session,
    agent: Agent,
    storage: StorageProvider | None = None,
) -> Agent:
    """
    Remove the avatar for *agent*.

    Deletes file from storage (best-effort) and clears avatar metadata.
    Returns the updated Agent ORM object.
    """
    if not agent.avatar_file_key:
        # No avatar — nothing to do
        return agent

    resolved = _resolve_storage(storage)
    _delete_old_avatar(agent, resolved)

    agent.avatar_file_key = None
    agent.avatar_mime_type = None
    agent.avatar_size_bytes = None
    agent.avatar_updated_at = None

    db.commit()
    db.refresh(agent)
    return agent


def get_avatar_url(agent: Agent, storage: StorageProvider | None = None) -> str | None:
    """
    Return a URL for the agent's avatar, or None if no avatar or storage not configured.
    """
    if not agent.avatar_file_key:
        return None
    try:
        resolved = storage or get_storage_provider()
        return resolved.generate_presigned_url(agent.avatar_file_key)
    except StorageError:
        return None
