"""
Tests for LocalStorageProvider and get_storage_provider factory.

All tests use pytest's tmp_path fixture — no files are written to the
project's ./storage directory.
"""

import os
from unittest.mock import patch

import pytest

from app.services.storage.base import StorageError
from app.services.storage.factory import get_storage_provider
from app.services.storage.local import LocalStorageProvider

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def provider(tmp_path):
    return LocalStorageProvider(root_path=str(tmp_path))


# ── Basic operations ──────────────────────────────────────────────────────────

def test_put_and_get_file(provider):
    provider.put_file("hello.txt", b"world")
    assert provider.get_file("hello.txt") == b"world"


def test_put_overwrites_existing(provider):
    provider.put_file("file.bin", b"v1")
    provider.put_file("file.bin", b"v2")
    assert provider.get_file("file.bin") == b"v2"


def test_exists_returns_true_after_put(provider):
    provider.put_file("doc.txt", b"content")
    assert provider.exists("doc.txt") is True


def test_exists_returns_false_before_put(provider):
    assert provider.exists("nonexistent.txt") is False


def test_delete_file_removes_it(provider):
    provider.put_file("todelete.txt", b"bye")
    provider.delete_file("todelete.txt")
    assert provider.exists("todelete.txt") is False


def test_delete_nonexistent_file_is_noop(provider):
    # Must not raise — idempotent
    provider.delete_file("ghost.txt")


def test_get_nonexistent_file_raises(provider):
    with pytest.raises(StorageError, match="Arquivo não encontrado"):
        provider.get_file("missing.txt")


def test_put_accepts_content_type_kwarg(provider):
    # content_type is accepted but not stored locally — just must not raise
    provider.put_file("img.png", b"\x89PNG", content_type="image/png")
    assert provider.get_file("img.png") == b"\x89PNG"


# ── Subdirectories ────────────────────────────────────────────────────────────

def test_subdirectories_are_created_automatically(provider, tmp_path):
    key = "workspaces/abc123/sources/xyz/original/file.txt"
    provider.put_file(key, b"nested content")
    full_path = tmp_path / "workspaces" / "abc123" / "sources" / "xyz" / "original" / "file.txt"
    assert full_path.exists()
    assert full_path.read_bytes() == b"nested content"


def test_file_is_stored_inside_root(provider, tmp_path):
    provider.put_file("sub/dir/file.dat", b"data")
    resolved = os.path.abspath(str(tmp_path / "sub" / "dir" / "file.dat"))
    assert resolved.startswith(str(tmp_path))


# ── Path traversal security ───────────────────────────────────────────────────

def test_traversal_with_dotdot_blocked(provider):
    with pytest.raises(StorageError):
        provider.put_file("../evil.txt", b"bad")


def test_traversal_nested_dotdot_blocked(provider):
    with pytest.raises(StorageError):
        provider.get_file("sub/../../etc/passwd")


def test_absolute_path_blocked(provider):
    with pytest.raises(StorageError):
        provider.put_file("/etc/passwd", b"bad")


def test_key_with_null_byte_blocked(provider):
    # Null bytes in filenames are rejected by the OS; ensure StorageError, not crash.
    with pytest.raises((StorageError, ValueError, OSError)):
        provider.put_file("file\x00.txt", b"bad")


def test_empty_key_blocked(provider):
    with pytest.raises(StorageError):
        provider.put_file("", b"data")


def test_blank_key_blocked(provider):
    with pytest.raises(StorageError):
        provider.put_file("   ", b"data")


def test_key_that_normalizes_outside_root_is_blocked(provider, tmp_path):
    # Construct a key that looks local but resolves outside after normalization
    # e.g. "sub/../../../outside"
    with pytest.raises(StorageError):
        provider.put_file("sub/../../../outside.txt", b"bad")


def test_normal_key_with_subdirs_is_allowed(provider):
    provider.put_file("workspaces/uuid-123/kb/uuid-456/file.txt", b"ok")
    assert provider.exists("workspaces/uuid-123/kb/uuid-456/file.txt") is True


# ── Constructor ───────────────────────────────────────────────────────────────

def test_empty_root_path_raises():
    with pytest.raises(StorageError):
        LocalStorageProvider(root_path="")


# ── Factory ───────────────────────────────────────────────────────────────────

def test_factory_local_returns_local_provider(tmp_path):
    with patch("app.services.storage.factory.settings") as mock_settings:
        mock_settings.storage_provider = "local"
        mock_settings.storage_local_root = str(tmp_path)
        result = get_storage_provider()
    assert isinstance(result, LocalStorageProvider)


def test_factory_s3_raises_without_config():
    with patch("app.services.storage.factory.settings") as mock_settings:
        mock_settings.storage_provider = "s3"
        mock_settings.storage_bucket = ""
        mock_settings.storage_endpoint_url = ""
        mock_settings.storage_access_key_id = ""
        mock_settings.storage_secret_access_key = ""
        mock_settings.storage_region = "us-east-1"
        with pytest.raises(StorageError):
            get_storage_provider()


def test_factory_unknown_provider_raises():
    with patch("app.services.storage.factory.settings") as mock_settings:
        mock_settings.storage_provider = "azure"
        with pytest.raises(StorageError, match="Provedor de armazenamento desconhecido"):
            get_storage_provider()


def test_factory_empty_provider_raises():
    with patch("app.services.storage.factory.settings") as mock_settings:
        mock_settings.storage_provider = ""
        with pytest.raises(StorageError, match="Provedor de armazenamento desconhecido"):
            get_storage_provider()
