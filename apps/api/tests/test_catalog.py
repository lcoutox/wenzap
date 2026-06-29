"""
Tests for the Catalog module (categories + items).

Coverage:
- CRUD for categories and items
- Tenant isolation (cross-workspace access returns 404)
- RBAC (viewer cannot write, member can, admin can delete category)
- searchable_text generation
- metadata_json validation
- Item filters (status, category, q, tag, has_price, is_featured)
- Archive pattern for items, soft-delete for categories
"""

import uuid

from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup(db: Session):
    owner = _make_user(db, f"cat-owner-{uuid.uuid4().hex[:6]}@test.com", "Cat Owner")
    ws = _make_workspace(db, owner, f"cat-ws-{uuid.uuid4().hex[:6]}", "Cat Workspace")
    db.commit()
    return owner, ws


def _make_viewer(db: Session, workspace: Workspace) -> User:
    viewer = _make_user(db, f"viewer-{uuid.uuid4().hex[:6]}@test.com", "Viewer")
    m = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=viewer.id,
        role=MemberRole.viewer,
        status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return viewer


def _make_member_user(db: Session, workspace: Workspace) -> User:
    member = _make_user(db, f"member-{uuid.uuid4().hex[:6]}@test.com", "Member")
    m = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=member.id,
        role=MemberRole.member,
        status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    return member


# ── Category tests ────────────────────────────────────────────────────────────

class TestCategories:
    def test_create_category_returns_201(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            r = client.post("/catalog/categories", json={"name": "Veículos"})
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Veículos"
        assert body["is_active"] is True
        assert body["workspace_id"] == str(ws.id)

    def test_list_categories(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/categories", json={"name": "A"})
            client.post("/catalog/categories", json={"name": "B"})
            r = client.get("/catalog/categories")
        assert r.status_code == 200
        names = [c["name"] for c in r.json()]
        assert "A" in names and "B" in names

    def test_viewer_can_read_categories(self, db: Session):
        owner, ws = _setup(db)
        viewer = _make_viewer(db, ws)
        with _make_client(db, viewer, ws) as client:
            r = client.get("/catalog/categories")
        assert r.status_code == 200

    def test_viewer_cannot_create_category(self, db: Session):
        owner, ws = _setup(db)
        viewer = _make_viewer(db, ws)
        with _make_client(db, viewer, ws) as client:
            r = client.post("/catalog/categories", json={"name": "X"})
        assert r.status_code == 403

    def test_update_category(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            cat_id = client.post("/catalog/categories", json={"name": "Old"}).json()["id"]
            r = client.patch(
                f"/catalog/categories/{cat_id}", json={"name": "New", "description": "desc"}
            )
        assert r.status_code == 200
        assert r.json()["name"] == "New"
        assert r.json()["description"] == "desc"

    def test_delete_category_soft_deletes(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            cat_id = client.post("/catalog/categories", json={"name": "ToDelete"}).json()["id"]
            r = client.delete(f"/catalog/categories/{cat_id}")
        assert r.status_code == 200
        assert r.json()["is_active"] is False

    def test_deleted_category_hidden_from_list(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            cat_id = client.post("/catalog/categories", json={"name": "Hidden"}).json()["id"]
            client.delete(f"/catalog/categories/{cat_id}")
            r = client.get("/catalog/categories")
        ids = [c["id"] for c in r.json()]
        assert cat_id not in ids

    def test_category_parent_id(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            parent_id = client.post("/catalog/categories", json={"name": "Parent"}).json()["id"]
            r = client.post("/catalog/categories", json={"name": "Child", "parent_id": parent_id})
        assert r.status_code == 201
        assert r.json()["parent_id"] == parent_id

    def test_cannot_access_category_from_other_workspace(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as client_a:
            cat_id = client_a.post("/catalog/categories", json={"name": "Private"}).json()["id"]
        with _make_client(db, owner_b, ws_b) as client_b:
            r = client_b.get(f"/catalog/categories/{cat_id}")
        assert r.status_code == 404


# ── Item tests ────────────────────────────────────────────────────────────────

class TestItems:
    def test_create_item_returns_201(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            r = client.post("/catalog/items", json={
                "name": "Corolla XEI 2021",
                "price": 88900.00,
                "currency": "BRL",
                "status": "active",
            })
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Corolla XEI 2021"
        assert body["status"] == "active"
        assert body["workspace_id"] == str(ws.id)

    def test_searchable_text_is_generated(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            r = client.post("/catalog/items", json={
                "name": "Corolla XEI",
                "short_description": "Sedan automático",
                "price": 88900.00,
                "tags": ["seminovo", "automático"],
                "sku": "CRL-001",
            })
        body = r.json()
        text = body["searchable_text"] or ""
        assert "Corolla XEI" in text
        assert "Sedan automático" in text
        assert "SKU: CRL-001" in text
        assert "seminovo" in text

    def test_metadata_json_accepted(self, db: Session):
        owner, ws = _setup(db)
        meta = {"brand": "Toyota", "year": 2021, "km": 42000}
        with _make_client(db, owner, ws) as client:
            r = client.post("/catalog/items", json={"name": "Car", "metadata_json": meta})
        assert r.status_code == 201
        assert r.json()["metadata_json"]["brand"] == "Toyota"

    def test_metadata_json_must_be_object(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            r = client.post(
                "/catalog/items", json={"name": "X", "metadata_json": ["not", "object"]}
            )
        assert r.status_code == 422

    def test_invalid_status_rejected(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            r = client.post("/catalog/items", json={"name": "X", "status": "published"})
        assert r.status_code == 422

    def test_viewer_cannot_create_item(self, db: Session):
        owner, ws = _setup(db)
        viewer = _make_viewer(db, ws)
        with _make_client(db, viewer, ws) as client:
            r = client.post("/catalog/items", json={"name": "X"})
        assert r.status_code == 403

    def test_member_can_create_item(self, db: Session):
        owner, ws = _setup(db)
        member = _make_member_user(db, ws)
        with _make_client(db, member, ws) as client:
            r = client.post("/catalog/items", json={"name": "By Member"})
        assert r.status_code == 201

    def test_list_items(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "Item 1"})
            client.post("/catalog/items", json={"name": "Item 2"})
            r = client.get("/catalog/items")
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_filter_by_status(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "Active", "status": "active"})
            client.post("/catalog/items", json={"name": "Draft", "status": "draft"})
            r = client.get("/catalog/items?status=draft")
        names = [i["name"] for i in r.json()]
        assert "Draft" in names
        assert "Active" not in names

    def test_filter_by_q(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "Toyota Corolla", "sku": "TOYOTA-001"})
            client.post("/catalog/items", json={"name": "Honda Civic"})
            r = client.get("/catalog/items?q=toyota")
        names = [i["name"] for i in r.json()]
        assert "Toyota Corolla" in names
        assert "Honda Civic" not in names

    def test_filter_by_tag(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "Taggged", "tags": ["promo", "destaque"]})
            client.post("/catalog/items", json={"name": "Untagged"})
            r = client.get("/catalog/items?tag=promo")
        names = [i["name"] for i in r.json()]
        assert "Taggged" in names
        assert "Untagged" not in names

    def test_filter_has_price_true(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "With Price", "price": 99.90})
            client.post("/catalog/items", json={"name": "No Price"})
            r = client.get("/catalog/items?has_price=true")
        names = [i["name"] for i in r.json()]
        assert "With Price" in names
        assert "No Price" not in names

    def test_filter_by_category(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            cat_id = client.post("/catalog/categories", json={"name": "Carros"}).json()["id"]
            client.post("/catalog/items", json={"name": "In Cat", "category_id": cat_id})
            client.post("/catalog/items", json={"name": "No Cat"})
            r = client.get(f"/catalog/items?category_id={cat_id}")
        names = [i["name"] for i in r.json()]
        assert "In Cat" in names
        assert "No Cat" not in names

    def test_update_item(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = client.post("/catalog/items", json={"name": "Old Name"}).json()["id"]
            r = client.patch(f"/catalog/items/{item_id}", json={"name": "New Name", "price": 200.0})
        assert r.status_code == 200
        assert r.json()["name"] == "New Name"

    def test_archive_item_removes_from_list(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = client.post("/catalog/items", json={"name": "To Archive"}).json()["id"]
            r_del = client.delete(f"/catalog/items/{item_id}")
            assert r_del.json()["status"] == "archived"
            r_list = client.get("/catalog/items")
        ids = [i["id"] for i in r_list.json()]
        assert item_id not in ids

    def test_cannot_access_item_from_other_workspace(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as client_a:
            item_id = client_a.post("/catalog/items", json={"name": "Private"}).json()["id"]
        with _make_client(db, owner_b, ws_b) as client_b:
            r = client_b.get(f"/catalog/items/{item_id}")
        assert r.status_code == 404

    def test_list_does_not_return_other_workspace_items(self, db: Session):
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)
        with _make_client(db, owner_a, ws_a) as c_a:
            item_id = c_a.post("/catalog/items", json={"name": "WS-A Item"}).json()["id"]
        with _make_client(db, owner_b, ws_b) as c_b:
            r = c_b.get("/catalog/items")
        ids = [i["id"] for i in r.json()]
        assert item_id not in ids

    def test_is_featured_filter(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "Featured", "is_featured": True})
            client.post("/catalog/items", json={"name": "Normal", "is_featured": False})
            r = client.get("/catalog/items?is_featured=true")
        names = [i["name"] for i in r.json()]
        assert "Featured" in names
        assert "Normal" not in names


# ── include_primary_media tests ───────────────────────────────────────────────

class TestIncludePrimaryMedia:
    def test_without_flag_primary_media_is_null(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "Item A"})
            r = client.get("/catalog/items")
        item = r.json()[0]
        assert item.get("primary_media") is None

    def test_with_flag_no_media_returns_null(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            client.post("/catalog/items", json={"name": "No Media"})
            r = client.get("/catalog/items?include_primary_media=true")
        item = r.json()[0]
        assert item["primary_media"] is None

    def test_with_flag_returns_primary_media(self, db: Session):
        from io import BytesIO
        from unittest.mock import patch

        from app.services.storage.base import StorageProvider

        class _MockStorage(StorageProvider):
            def put_file(self, key, data, content_type=None): self._store[key] = data
            def get_file(self, key): return b""
            def delete_file(self, key): pass
            def exists(self, key): return True
            def generate_presigned_url(self, key, expires_in=3600):
                return f"https://mock/{key}"
            def __init__(self): self._store = {}

        mock_storage = _MockStorage()
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            item_id = client.post("/catalog/items", json={"name": "With Media"}).json()["id"]
            # Upload primary image
            with patch(
                "app.services.catalog_media_service.get_storage_or_503",
                return_value=mock_storage,
            ):
                client.post(
                    f"/catalog/items/{item_id}/media",
                    files={"file": (
                        "photo.jpg", BytesIO(b"\xff\xd8\xff" + b"\x00" * 50), "image/jpeg"
                    )},
                )
            # List with include_primary_media
            with patch(
                "app.routers.catalog.catalog_media_service.get_storage_or_503",
                return_value=mock_storage,
            ):
                r = client.get("/catalog/items?include_primary_media=true")

        items = {i["id"]: i for i in r.json()}
        pm = items[item_id]["primary_media"]
        assert pm is not None
        assert pm["file_type"] == "image"
        assert pm["is_primary"] is True
        assert pm["preview_url"] is not None
        assert "mock" in pm["preview_url"]

    def test_does_not_return_other_workspace_primary_media(self, db: Session):
        from io import BytesIO
        from unittest.mock import patch

        from app.services.storage.base import StorageProvider

        class _MockStorage(StorageProvider):
            def put_file(self, key, data, content_type=None): pass
            def get_file(self, key): return b""
            def delete_file(self, key): pass
            def exists(self, key): return True
            def generate_presigned_url(self, key, expires_in=3600): return f"https://mock/{key}"
            def __init__(self): pass

        mock = _MockStorage()
        owner_a, ws_a = _setup(db)
        owner_b, ws_b = _setup(db)

        # Upload media for workspace A's item
        with _make_client(db, owner_a, ws_a) as ca:
            item_id_a = ca.post("/catalog/items", json={"name": "WS-A"}).json()["id"]
            with patch("app.services.catalog_media_service.get_storage_or_503", return_value=mock):
                ca.post(
                    f"/catalog/items/{item_id_a}/media",
                    files={"file": ("a.jpg", BytesIO(b"\xff\xd8\xff" + b"\x00"*50), "image/jpeg")},
                )

        # WS-B list should not see WS-A primary media
        with _make_client(db, owner_b, ws_b) as cb:
            cb.post("/catalog/items", json={"name": "WS-B"})
            patch_target = "app.routers.catalog.catalog_media_service.get_storage_or_503"
            with patch(patch_target, return_value=mock):
                r = cb.get("/catalog/items?include_primary_media=true")

        for item in r.json():
            assert item["primary_media"] is None

    def test_multiple_items_get_correct_primary_media(self, db: Session):
        from io import BytesIO
        from unittest.mock import patch

        from app.services.storage.base import StorageProvider

        class _MockStorage(StorageProvider):
            def put_file(self, key, data, content_type=None): pass
            def get_file(self, key): return b""
            def delete_file(self, key): pass
            def exists(self, key): return True
            def generate_presigned_url(self, key, expires_in=3600): return f"https://mock/{key}"
            def __init__(self): pass

        mock = _MockStorage()
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            id1 = client.post("/catalog/items", json={"name": "Item 1"}).json()["id"]
            id2 = client.post("/catalog/items", json={"name": "Item 2"}).json()["id"]
            # only item1 gets a primary image
            with patch("app.services.catalog_media_service.get_storage_or_503", return_value=mock):
                client.post(
                    f"/catalog/items/{id1}/media",
                    files={"file": (
                        "a.jpg", BytesIO(b"\xff\xd8\xff" + b"\x00" * 50), "image/jpeg"
                    )},
                )
            router_patch = "app.routers.catalog.catalog_media_service.get_storage_or_503"
            with patch(router_patch, return_value=mock):
                r = client.get("/catalog/items?include_primary_media=true")

        by_id = {i["id"]: i for i in r.json()}
        assert by_id[id1]["primary_media"] is not None
        assert by_id[id2]["primary_media"] is None
