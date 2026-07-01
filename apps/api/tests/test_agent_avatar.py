"""
Tests for agent avatar upload/delete — Phase Agent UX.2.

Covers:
- upload valid image (jpeg, png, webp)
- reject invalid MIME / content mismatch
- reject file above size limit
- replacing avatar removes old file from storage
- delete avatar clears metadata
- cross-workspace isolation
- storage not configured returns 503
- AgentOut includes avatar_url (when URL available)
"""

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.agent_avatar_service import (
    _ALLOWED_MIMES,
    _MAX_SIZE_BYTES,
    _validate_image,
    delete_avatar,
    get_avatar_url,
    upload_avatar,
)
from app.services.storage.base import StorageError
from tests.conftest import _make_ai_model, _make_client, _make_user

# ── Image magic bytes helpers ─────────────────────────────────────────────────

JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 100
PNG_MAGIC = b"\x89PNG" + b"\x00" * 100
WEBP_MAGIC = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 100


def _fake_agent(workspace_id=None, agent_id=None, avatar_file_key=None):
    agent = MagicMock()
    agent.workspace_id = workspace_id or uuid.uuid4()
    agent.id = agent_id or uuid.uuid4()
    agent.avatar_file_key = avatar_file_key
    agent.avatar_mime_type = None
    agent.avatar_size_bytes = None
    agent.avatar_updated_at = None
    return agent


def _fake_db():
    db = MagicMock()
    db.commit.return_value = None
    db.refresh.return_value = None
    return db


def _fake_storage():
    storage = MagicMock()
    storage.put_file.return_value = None
    storage.delete_file.return_value = None
    storage.generate_presigned_url.return_value = "https://cdn.example.com/avatar.jpg"
    return storage


# ── _validate_image ────────────────────────────────────────────────────────────

def test_validate_image_jpeg():
    mime = _validate_image(JPEG_MAGIC, "image/jpeg")
    assert mime == "image/jpeg"


def test_validate_image_png():
    mime = _validate_image(PNG_MAGIC, "image/png")
    assert mime == "image/png"


def test_validate_image_webp():
    mime = _validate_image(WEBP_MAGIC, "image/webp")
    assert mime == "image/webp"


def test_validate_image_detects_by_magic_regardless_of_declared_mime():
    # Magic bytes win: JPEG data declared as png still resolves to jpeg
    mime = _validate_image(JPEG_MAGIC, "image/png")
    assert mime == "image/jpeg"


def test_validate_image_rejects_too_large():
    from fastapi import HTTPException
    oversized = b"\xff\xd8\xff" + b"x" * (_MAX_SIZE_BYTES + 1)
    with pytest.raises(HTTPException) as exc_info:
        _validate_image(oversized, "image/jpeg")
    assert exc_info.value.status_code == 413


def test_validate_image_rejects_unknown_data():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _validate_image(b"PK\x03\x04" + b"\x00" * 100, "application/zip")
    assert exc_info.value.status_code == 400


def test_validate_image_rejects_declared_mime_with_wrong_magic():
    from fastapi import HTTPException
    # Declares image/jpeg but content is a ZIP
    with pytest.raises(HTTPException) as exc_info:
        _validate_image(b"PK\x03\x04" + b"\x00" * 100, "image/jpeg")
    assert exc_info.value.status_code == 400


# ── upload_avatar ─────────────────────────────────────────────────────────────

def test_upload_avatar_saves_file_and_updates_agent():
    agent = _fake_agent()
    db = _fake_db()
    storage = _fake_storage()

    result = upload_avatar(db, agent, JPEG_MAGIC, "photo.jpg", "image/jpeg", storage=storage)

    storage.put_file.assert_called_once()
    key_used = storage.put_file.call_args[0][0]
    assert f"workspaces/{agent.workspace_id}/agents/{agent.id}/avatar/" in key_used
    assert result.avatar_mime_type == "image/jpeg"
    assert result.avatar_size_bytes == len(JPEG_MAGIC)
    assert result.avatar_updated_at is not None


def test_upload_avatar_removes_old_file_when_replacing():
    old_key = "workspaces/ws/agents/ag/avatar/old-avatar.jpg"
    agent = _fake_agent(avatar_file_key=old_key)
    db = _fake_db()
    storage = _fake_storage()

    upload_avatar(db, agent, PNG_MAGIC, "new.png", "image/png", storage=storage)

    # Should have called delete_file with the old key
    storage.delete_file.assert_called_with(old_key)


def test_upload_avatar_raises_503_if_storage_fails_on_put():
    from fastapi import HTTPException
    agent = _fake_agent()
    db = _fake_db()
    storage = _fake_storage()
    storage.put_file.side_effect = StorageError("Connection refused")

    with pytest.raises(HTTPException) as exc_info:
        upload_avatar(db, agent, JPEG_MAGIC, "photo.jpg", "image/jpeg", storage=storage)
    assert exc_info.value.status_code == 503


# ── delete_avatar ─────────────────────────────────────────────────────────────

def test_delete_avatar_removes_file_and_clears_fields():
    old_key = "workspaces/ws/agents/ag/avatar/old.jpg"
    agent = _fake_agent(avatar_file_key=old_key)
    db = _fake_db()
    storage = _fake_storage()

    result = delete_avatar(db, agent, storage=storage)

    storage.delete_file.assert_called_with(old_key)
    assert result.avatar_file_key is None
    assert result.avatar_mime_type is None
    assert result.avatar_size_bytes is None
    assert result.avatar_updated_at is None


def test_delete_avatar_no_op_if_no_avatar():
    agent = _fake_agent(avatar_file_key=None)
    db = _fake_db()
    storage = _fake_storage()

    result = delete_avatar(db, agent, storage=storage)

    storage.delete_file.assert_not_called()
    assert result is agent


def test_delete_avatar_is_best_effort_if_storage_delete_fails():
    old_key = "workspaces/ws/agents/ag/avatar/gone.jpg"
    agent = _fake_agent(avatar_file_key=old_key)
    db = _fake_db()
    storage = _fake_storage()
    storage.delete_file.side_effect = StorageError("Not found")

    # Should NOT raise — best-effort deletion
    result = delete_avatar(db, agent, storage=storage)
    assert result.avatar_file_key is None


# ── get_avatar_url ────────────────────────────────────────────────────────────

def test_get_avatar_url_returns_url_when_configured():
    agent = _fake_agent(avatar_file_key="workspaces/w/agents/a/avatar/img.jpg")
    storage = _fake_storage()
    url = get_avatar_url(agent, storage=storage)
    assert url == "https://cdn.example.com/avatar.jpg"


def test_get_avatar_url_returns_none_if_no_key():
    agent = _fake_agent(avatar_file_key=None)
    storage = _fake_storage()
    url = get_avatar_url(agent, storage=storage)
    assert url is None


def test_get_avatar_url_returns_none_if_storage_not_configured():
    agent = _fake_agent(avatar_file_key="some/key")
    with patch(
        "app.services.agent_avatar_service.get_storage_provider",
        side_effect=StorageError("not configured"),
    ):
        url = get_avatar_url(agent, storage=None)
    assert url is None


# ── Integration: HTTP endpoints ───────────────────────────────────────────────

@pytest.fixture()
def agent_with_avatar_setup(db, client_a, subscription_a, ai_model):
    """Create an agent and return its id."""
    resp = client_a.post(
        "/agents",
        json={
            "name": "Avatar Agent",
            "system_prompt": "test",
            "ai_model_id": str(ai_model.id),
            "temperature": 0.7,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _fake_storage_patch():
    storage = _fake_storage()
    return patch(
        "app.services.agent_avatar_service.get_storage_provider",
        return_value=storage,
    ), storage


def test_upload_avatar_endpoint_returns_200_with_avatar_url(
    client_a, subscription_a, ai_model, agent_with_avatar_setup
):
    agent_id = agent_with_avatar_setup
    patcher, storage = _fake_storage_patch()
    with patcher:
        resp = client_a.post(
            f"/agents/{agent_id}/avatar",
            files={"file": ("photo.jpg", io.BytesIO(JPEG_MAGIC), "image/jpeg")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["avatar_url"] == "https://cdn.example.com/avatar.jpg"
    assert body["avatar_mime_type"] == "image/jpeg"
    assert body["avatar_updated_at"] is not None


def test_upload_avatar_endpoint_rejects_invalid_type(
    client_a, subscription_a, ai_model, agent_with_avatar_setup
):
    agent_id = agent_with_avatar_setup
    patcher, _ = _fake_storage_patch()
    with patcher:
        resp = client_a.post(
            f"/agents/{agent_id}/avatar",
            files={"file": ("bad.txt", io.BytesIO(b"not an image" * 10), "text/plain")},
        )
    assert resp.status_code == 400


def test_upload_avatar_endpoint_rejects_oversized(
    client_a, subscription_a, ai_model, agent_with_avatar_setup
):
    agent_id = agent_with_avatar_setup
    patcher, _ = _fake_storage_patch()
    oversized = JPEG_MAGIC + b"x" * (_MAX_SIZE_BYTES + 1)
    with patcher:
        resp = client_a.post(
            f"/agents/{agent_id}/avatar",
            files={"file": ("big.jpg", io.BytesIO(oversized), "image/jpeg")},
        )
    assert resp.status_code == 413


def test_delete_avatar_endpoint_clears_fields(
    client_a, subscription_a, ai_model, agent_with_avatar_setup
):
    agent_id = agent_with_avatar_setup
    patcher, _ = _fake_storage_patch()

    # First upload
    with patcher:
        client_a.post(
            f"/agents/{agent_id}/avatar",
            files={"file": ("photo.jpg", io.BytesIO(JPEG_MAGIC), "image/jpeg")},
        )

    # Then delete
    with patcher:
        resp = client_a.delete(f"/agents/{agent_id}/avatar")
    assert resp.status_code == 200
    body = resp.json()
    assert body["avatar_url"] is None
    assert body["avatar_mime_type"] is None
    assert body["avatar_updated_at"] is None


def test_avatar_endpoint_cross_workspace_isolation(
    db, subscription_a, subscription_b, ai_model
):
    """Workspace B must not be able to touch workspace A's agents."""
    from app.models.agent import Agent as AgentModel
    from app.models.workspace import Workspace as WorkspaceModel
    from tests.conftest import _make_client, _make_user

    # Create workspace_a and its agent outside of client fixtures
    from sqlalchemy import select
    ws_a = db.scalar(select(WorkspaceModel).where(WorkspaceModel.id == subscription_a.workspace_id))
    ws_b = db.scalar(select(WorkspaceModel).where(WorkspaceModel.id == subscription_b.workspace_id))

    # Create agent in ws_a
    agent = AgentModel(
        workspace_id=ws_a.id,
        name="WS-A Agent",
        ai_model_id=ai_model.id,
        model_name=ai_model.model_name,
        system_prompt="test",
    )
    db.add(agent)
    db.flush()
    agent_id = agent.id
    db.commit()

    # Find or create a user in ws_b
    from tests.conftest import _make_user
    user_b_obj = _make_user(db, "cross_test_user@test.com", "Cross Test")
    from app.enums import MemberRole, MemberStatus
    from app.models.workspace_member import WorkspaceMember
    db.add(WorkspaceMember(
        workspace_id=ws_b.id,
        user_id=user_b_obj.id,
        role=MemberRole.member.value,
        status=MemberStatus.active.value,
    ))
    db.commit()

    patcher, _ = _fake_storage_patch()
    with _make_client(db, user_b_obj, ws_b) as cb:
        with patcher:
            resp = cb.post(
                f"/agents/{agent_id}/avatar",
                files={"file": ("photo.jpg", io.BytesIO(JPEG_MAGIC), "image/jpeg")},
            )
    assert resp.status_code == 404


def test_upload_avatar_endpoint_503_if_storage_not_configured(
    client_a, subscription_a, ai_model, agent_with_avatar_setup
):
    agent_id = agent_with_avatar_setup
    with patch(
        "app.services.agent_avatar_service.get_storage_provider",
        side_effect=StorageError("Unknown provider"),
    ):
        resp = client_a.post(
            f"/agents/{agent_id}/avatar",
            files={"file": ("photo.jpg", io.BytesIO(JPEG_MAGIC), "image/jpeg")},
        )
    assert resp.status_code == 503
