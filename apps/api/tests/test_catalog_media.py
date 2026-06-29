"""
Tests for Catálogo.2 — R2 Media: upload, list, update, delete, set-primary, reorder.

Storage is always mocked (MockStorageProvider) so no real R2/S3 is needed.
"""

import uuid
from io import BytesIO
from unittest.mock import patch

from sqlalchemy.orm import Session

from app.services.storage.base import StorageError, StorageProvider
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Mock storage ──────────────────────────────────────────────────────────────

class MockStorageProvider(StorageProvider):
    """In-memory storage provider for tests."""

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    def put_file(self, key: str, data: bytes, content_type: str | None = None) -> None:
        self._store[key] = data

    def get_file(self, key: str) -> bytes:
        if key not in self._store:
            raise StorageError(f"Not found: {key}")
        return self._store[key]

    def delete_file(self, key: str) -> None:
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._store

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://mock-storage/{key}?expires={expires_in}"


class BrokenStorageProvider(StorageProvider):
    """Always fails put_file — used to test storage error handling."""

    def put_file(self, key: str, data: bytes, content_type: str | None = None) -> None:
        raise StorageError("Storage unavailable")

    def get_file(self, key: str) -> bytes:
        raise StorageError("Storage unavailable")

    def delete_file(self, key: str) -> None:
        raise StorageError("Storage unavailable")

    def exists(self, key: str) -> bool:
        return False

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        raise StorageError("Storage unavailable")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup(db: Session):
    owner = _make_user(db, f"media-owner-{uuid.uuid4().hex[:6]}@test.com", "Owner")
    ws = _make_workspace(db, owner, f"media-ws-{uuid.uuid4().hex[:6]}", "Media WS")
    db.commit()
    return owner, ws


FAKE_JPEG = b"\xff\xd8\xff" + b"\x00" * 100
FAKE_PNG  = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
FAKE_PDF  = b"%PDF-1.4" + b"\x00" * 100

_STORAGE_PATCH = "app.services.catalog_media_service.get_storage_or_503"


def _patch_storage(storage=None):
    if storage is None:
        storage = MockStorageProvider()
    return patch(_STORAGE_PATCH, return_value=storage)


def _create_item(client, name="Test Item"):
    r = client.post("/catalog/items", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload(client, item_id, *, filename="photo.jpg", data=FAKE_JPEG, ct="image/jpeg", **form):
    files = {"file": (filename, BytesIO(data), ct)}
    with _patch_storage():
        return client.post(f"/catalog/items/{item_id}/media", files=files, data=form)


# ── Upload tests ──────────────────────────────────────────────────────────────

class TestUpload:
    def test_upload_jpeg_returns_201(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r = _upload(client, item_id)
        assert r.status_code == 201
        body = r.json()
        assert body["file_type"] == "image"
        assert body["mime_type"] == "image/jpeg"
        assert body["is_primary"] is True  # first image auto-primary

    def test_upload_png_returns_201(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r = _upload(client, item_id, filename="img.png", data=FAKE_PNG, ct="image/png")
        assert r.status_code == 201
        assert r.json()["file_type"] == "image"

    def test_upload_pdf_returns_201(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r = _upload(client, item_id, filename="doc.pdf", data=FAKE_PDF, ct="application/pdf")
        assert r.status_code == 201
        body = r.json()
        assert body["file_type"] == "document"
        assert body["is_primary"] is False  # PDFs are never primary

    def test_upload_with_display_name_and_alt_text(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r = _upload(client, item_id, display_name="Foto principal", alt_text="Foto do carro")
        assert r.json()["display_name"] == "Foto principal"
        assert r.json()["alt_text"] == "Foto do carro"

    def test_response_includes_preview_url(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r = _upload(client, item_id)
        assert r.json()["preview_url"] is not None
        assert "mock-storage" in r.json()["preview_url"]

    def test_reject_invalid_mime_type(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r = _upload(client, item_id, filename="vid.mp4", data=b"\x00"*100, ct="video/mp4")
        assert r.status_code == 422
        assert "not allowed" in r.json()["detail"].lower()

    def test_reject_oversized_image(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            big = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)
            r = _upload(client, item_id, data=big)
        assert r.status_code == 422
        assert "large" in r.json()["detail"].lower()

    def test_reject_oversized_pdf(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            big = b"%PDF-1.4" + b"\x00" * (21 * 1024 * 1024)
            r = _upload(client, item_id, filename="big.pdf", data=big, ct="application/pdf")
        assert r.status_code == 422

    def test_reject_empty_file(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r = _upload(client, item_id, data=b"")
        assert r.status_code == 422

    def test_second_image_not_auto_primary(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            r1 = _upload(client, item_id, filename="a.jpg")
            r2 = _upload(client, item_id, filename="b.jpg")
        assert r1.json()["is_primary"] is True
        assert r2.json()["is_primary"] is False

    def test_cannot_upload_to_other_workspace_item(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as ca:
            item_id = _create_item(ca)
        with _make_client(db, owner_b, ws_b) as cb:
            r = _upload(cb, item_id)
        assert r.status_code == 404

    def test_storage_error_returns_503(self, db: Session):
        owner, ws = _setup(db)
        broken = BrokenStorageProvider()
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            with patch(_STORAGE_PATCH, return_value=broken):
                files = {"file": ("a.jpg", BytesIO(FAKE_JPEG), "image/jpeg")}
                r = client.post(f"/catalog/items/{item_id}/media", files=files)
        assert r.status_code == 503


# ── List tests ────────────────────────────────────────────────────────────────

class TestList:
    def test_list_returns_uploaded_media(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            _upload(client, item_id, filename="a.jpg")
            _upload(client, item_id, filename="b.jpg")
            with _patch_storage():
                r = client.get(f"/catalog/items/{item_id}/media")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_primary_image_sorted_first(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            _upload(client, item_id, filename="a.jpg")
            _upload(client, item_id, filename="b.jpg")
            with _patch_storage():
                r = client.get(f"/catalog/items/{item_id}/media")
        items = r.json()
        assert items[0]["is_primary"] is True

    def test_list_does_not_return_other_workspace_media(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as ca:
            item_id_a = _create_item(ca)
            _upload(ca, item_id_a)
        with _make_client(db, owner_b, ws_b) as cb:
            item_id_b = _create_item(cb)
            with _patch_storage():
                r = cb.get(f"/catalog/items/{item_id_b}/media")
        assert r.json() == []


# ── Update tests ──────────────────────────────────────────────────────────────

class TestUpdate:
    def test_update_display_name(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            media_id = _upload(client, item_id).json()["id"]
            with _patch_storage():
                r = client.patch(
                    f"/catalog/items/{item_id}/media/{media_id}",
                    json={"display_name": "Nova foto"},
                )
        assert r.status_code == 200
        assert r.json()["display_name"] == "Nova foto"

    def test_update_alt_text(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            media_id = _upload(client, item_id).json()["id"]
            with _patch_storage():
                r = client.patch(
                    f"/catalog/items/{item_id}/media/{media_id}",
                    json={"alt_text": "Foto do produto"},
                )
        assert r.json()["alt_text"] == "Foto do produto"

    def test_cannot_update_media_from_other_workspace(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as ca:
            item_id = _create_item(ca)
            media_id = _upload(ca, item_id).json()["id"]
        with _make_client(db, owner_b, ws_b) as cb:
            item_id_b = _create_item(cb)
            with _patch_storage():
                r = cb.patch(
                    f"/catalog/items/{item_id_b}/media/{media_id}",
                    json={"display_name": "hack"},
                )
        assert r.status_code == 404


# ── Delete tests ──────────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_media(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            media_id = _upload(client, item_id).json()["id"]
            with _patch_storage():
                r = client.delete(f"/catalog/items/{item_id}/media/{media_id}")
        assert r.status_code == 204

    def test_delete_primary_promotes_next(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            primary_id = _upload(client, item_id, filename="a.jpg").json()["id"]
            second_id = _upload(client, item_id, filename="b.jpg").json()["id"]
            with _patch_storage():
                client.delete(f"/catalog/items/{item_id}/media/{primary_id}")
                r = client.get(f"/catalog/items/{item_id}/media")
        items = r.json()
        assert len(items) == 1
        assert items[0]["id"] == second_id
        assert items[0]["is_primary"] is True

    def test_cannot_delete_media_from_other_workspace(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as ca:
            item_id = _create_item(ca)
            media_id = _upload(ca, item_id).json()["id"]
        with _make_client(db, owner_b, ws_b) as cb:
            item_id_b = _create_item(cb)
            with _patch_storage():
                r = cb.delete(f"/catalog/items/{item_id_b}/media/{media_id}")
        assert r.status_code == 404


# ── Set-primary tests ─────────────────────────────────────────────────────────

class TestSetPrimary:
    def test_set_primary_switches_primary(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            id1 = _upload(client, item_id, filename="a.jpg").json()["id"]
            id2 = _upload(client, item_id, filename="b.jpg").json()["id"]
            with _patch_storage():
                r = client.post(f"/catalog/items/{item_id}/media/{id2}/set-primary")
                assert r.status_code == 200
                assert r.json()["is_primary"] is True
                assert r.json()["id"] == id2
                # verify first is now not primary
                list_r = client.get(f"/catalog/items/{item_id}/media")
        items = {i["id"]: i for i in list_r.json()}
        assert items[id1]["is_primary"] is False
        assert items[id2]["is_primary"] is True

    def test_cannot_set_pdf_as_primary(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            pdf_id = _upload(
                client, item_id, filename="doc.pdf", data=FAKE_PDF, ct="application/pdf"
            ).json()["id"]
            with _patch_storage():
                r = client.post(f"/catalog/items/{item_id}/media/{pdf_id}/set-primary")
        assert r.status_code == 422

    def test_only_one_primary_per_item(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            _upload(client, item_id, filename="a.jpg")
            _upload(client, item_id, filename="b.jpg")
            id3 = _upload(client, item_id, filename="c.jpg").json()["id"]
            with _patch_storage():
                client.post(f"/catalog/items/{item_id}/media/{id3}/set-primary")
                r = client.get(f"/catalog/items/{item_id}/media")
        primaries = [i for i in r.json() if i["is_primary"]]
        assert len(primaries) == 1
        assert primaries[0]["id"] == id3


# ── Reorder tests ─────────────────────────────────────────────────────────────

class TestReorder:
    def test_reorder_updates_sort_order(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            id1 = _upload(client, item_id, filename="a.jpg").json()["id"]
            id2 = _upload(client, item_id, filename="b.jpg").json()["id"]
            with _patch_storage():
                r = client.post(
                    f"/catalog/items/{item_id}/media/reorder",
                    json=[
                        {"id": id1, "sort_order": 10},
                        {"id": id2, "sort_order": 0},
                    ],
                )
        assert r.status_code == 200
        # Primary still first (sort by is_primary desc, then sort_order asc)
        # id1 is primary; id2 has lower sort_order but primary wins
        by_id = {i["id"]: i for i in r.json()}
        assert by_id[id1]["sort_order"] == 10
        assert by_id[id2]["sort_order"] == 0

    def test_reorder_rejects_foreign_media_ids(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as ca:
            item_a = _create_item(ca)
            id_a = _upload(ca, item_a).json()["id"]
        with _make_client(db, owner_b, ws_b) as cb:
            item_b = _create_item(cb)
            with _patch_storage():
                r = cb.post(
                    f"/catalog/items/{item_b}/media/reorder",
                    json=[{"id": id_a, "sort_order": 0}],
                )
        assert r.status_code == 422


# ── Unconfigured storage tests ─────────────────────────────────────────────────

class TestUnconfiguredStorage:
    def test_list_returns_503_when_storage_unconfigured(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = _create_item(client)
            with patch(
                _STORAGE_PATCH,
                side_effect=__import__("fastapi").HTTPException(
                    status_code=503, detail="Storage não configurado."
                ),
            ):
                r = client.get(f"/catalog/items/{item_id}/media")
        assert r.status_code == 503
        assert "Storage" in r.json()["detail"]
