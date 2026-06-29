"""
Tests for Catálogo.8 — Catalog Import CSV/XLSX.
"""

import csv
import io
import json
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog_category import CatalogCategory
from app.models.catalog_item import CatalogItem
from tests.conftest import _make_client, _make_user, _make_workspace

# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup(db: Session):
    owner = _make_user(db, f"ci-{uuid.uuid4().hex[:6]}@t.com", "Import User")
    ws = _make_workspace(db, owner, f"ci-ws-{uuid.uuid4().hex[:6]}", "Import WS")
    db.commit()
    return owner, ws


def _csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def _make_xlsx(rows: list[dict]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _preview(client, file_bytes: bytes, filename: str = "items.csv",
             content_type: str = "text/csv"):
    return client.post(
        "/catalog/import/preview",
        files={"file": (filename, io.BytesIO(file_bytes), content_type)},
    )


def _commit(client, file_bytes: bytes, mapping: dict, mode: str = "create_only",
            filename: str = "items.csv", content_type: str = "text/csv"):
    return client.post(
        "/catalog/import/commit",
        files={"file": (filename, io.BytesIO(file_bytes), content_type)},
        data={"mapping_json": json.dumps(mapping), "mode": mode},
    )


@pytest.fixture(autouse=True)
def no_embed():
    with patch("app.services.catalog_import_service._try_embed_item"):
        yield


# ── Preview ───────────────────────────────────────────────────────────────────

class TestImportPreviewCSV:
    def test_preview_returns_columns_and_rows(self, db: Session):
        owner, ws = _setup(db)
        rows = [
            {"Nome": "Corolla", "Preço": "88900", "Categoria": "Seminovos"},
            {"Nome": "Civic",   "Preço": "79000", "Categoria": "Seminovos"},
        ]
        content = _csv_bytes(rows)
        with _make_client(db, owner, ws) as client:
            resp = _preview(client, content)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 2
        assert "Nome" in data["columns"]
        assert data["rows_preview"][0]["row_number"] == 2

    def test_preview_warns_on_image_column(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "X", "image_url": "http://x.com/img.jpg"}])
        with _make_client(db, owner, ws) as client:
            resp = _preview(client, content)
        assert resp.status_code == 200
        assert any("imagem" in w.lower() for w in resp.json()["warnings"])

    def test_preview_rejects_unsupported_type(self, db: Session):
        owner, ws = _setup(db)
        with _make_client(db, owner, ws) as client:
            resp = client.post(
                "/catalog/import/preview",
                files={"file": ("data.json", io.BytesIO(b"{}"), "application/json")},
            )
        assert resp.status_code == 422

    def test_preview_xlsx(self, db: Session):
        owner, ws = _setup(db)
        xlsx = _make_xlsx([{"Nome": "Corolla", "Preço": "88900"}])
        ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        with _make_client(db, owner, ws) as client:
            resp = _preview(client, xlsx, filename="items.xlsx", content_type=ct)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_rows"] == 1
        assert "Nome" in data["columns"]


# ── Commit — create_only ──────────────────────────────────────────────────────

class TestImportCommitCreateOnly:
    def test_creates_items(self, db: Session):
        owner, ws = _setup(db)
        rows = [
            {"Nome": "Corolla XEI 2021", "Preco": "88900"},
            {"Nome": "Civic EXL 2022",   "Preco": "79000"},
        ]
        content = _csv_bytes(rows)
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "price": "Preco"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] == 2
        assert data["errors"] == []

    def test_creates_missing_category(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "Produto X", "Categoria": "Nova Cat"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "category": "Categoria"})
        assert resp.status_code == 200
        assert resp.json()["created"] == 1
        cat = db.scalar(
            select(CatalogCategory).where(
                CatalogCategory.workspace_id == ws.id,
                CatalogCategory.name == "Nova Cat",
            )
        )
        assert cat is not None

    def test_normalizes_br_price_dot_comma(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "Item A", "Preco": "88.900,00"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "price": "Preco"})
        assert resp.status_code == 200
        assert resp.json()["created"] == 1
        item = db.scalar(
            select(CatalogItem).where(
                CatalogItem.workspace_id == ws.id,
                CatalogItem.name == "Item A",
            )
        )
        assert float(item.price) == pytest.approx(88900.0)

    def test_normalizes_br_price_r_dollar(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "Item B", "Preco": "R$ 1.250,99"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "price": "Preco"})
        assert resp.status_code == 200
        item = db.scalar(
            select(CatalogItem).where(
                CatalogItem.workspace_id == ws.id,
                CatalogItem.name == "Item B",
            )
        )
        assert float(item.price) == pytest.approx(1250.99)

    def test_normalizes_status_portuguese(self, db: Session):
        owner, ws = _setup(db)
        cases = [
            ("ativo", "active"), ("rascunho", "draft"), ("inativo", "inactive"),
            ("indisponível", "unavailable"), ("arquivado", "archived"),
        ]
        for pt, expected in cases:
            name = f"Stat-{pt}-{uuid.uuid4().hex[:4]}"
            content = _csv_bytes([{"Nome": name, "Status": pt}])
            with _make_client(db, owner, ws) as client:
                resp = _commit(client, content, {"name": "Nome", "status": "Status"})
            assert resp.status_code == 200
            item = db.scalar(
                select(CatalogItem).where(
                    CatalogItem.workspace_id == ws.id,
                    CatalogItem.name == name,
                )
            )
            assert item.status == expected

    def test_normalizes_tags(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "Item Tags", "Tags": "automático; sedan | seminovo, 2021"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "tags": "Tags"})
        assert resp.status_code == 200
        item = db.scalar(
            select(CatalogItem).where(
                CatalogItem.workspace_id == ws.id,
                CatalogItem.name == "Item Tags",
            )
        )
        assert set(item.tags) == {"automático", "sedan", "seminovo", "2021"}

    def test_metadata_from_extra_columns(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "Corolla", "Marca": "Toyota", "Ano": "2021"}])
        mapping = {"name": "Nome", "metadata": {"brand": "Marca", "year": "Ano"}}
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, mapping)
        assert resp.status_code == 200
        item = db.scalar(
            select(CatalogItem).where(
                CatalogItem.workspace_id == ws.id,
                CatalogItem.name == "Corolla",
            )
        )
        assert item.metadata_json["brand"] == "Toyota"
        assert item.metadata_json["year"] == "2021"

    def test_row_without_name_generates_error(self, db: Session):
        owner, ws = _setup(db)
        rows = [{"Nome": "Item OK", "Preco": "100"}, {"Nome": "", "Preco": "200"}]
        content = _csv_bytes(rows)
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "price": "Preco"})
        data = resp.json()
        assert data["created"] == 1
        assert data["skipped"] == 1
        assert any(e["field"] == "name" for e in data["errors"])

    def test_invalid_price_generates_row_error(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "Item X", "Preco": "not_a_price"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "price": "Preco"})
        data = resp.json()
        assert data["skipped"] == 1
        assert any(e["field"] == "price" for e in data["errors"])

    def test_image_column_generates_warning(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "Item Y", "image_url": "http://x.com/img.jpg"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome"})
        assert len(resp.json()["warnings"]) > 0

    def test_partial_import_on_row_errors(self, db: Session):
        owner, ws = _setup(db)
        rows = [
            {"Nome": "OK Item",  "Preco": "100"},
            {"Nome": "",         "Preco": "200"},
            {"Nome": "OK Item2", "Preco": "300"},
        ]
        content = _csv_bytes(rows)
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "price": "Preco"})
        data = resp.json()
        assert data["created"] == 2
        assert data["skipped"] == 1


# ── Commit — upsert ───────────────────────────────────────────────────────────

class TestImportCommitUpsert:
    def _make_existing(self, db: Session, ws_id: uuid.UUID, name: str,
                        sku: str | None = None, external_id: str | None = None) -> CatalogItem:
        item = CatalogItem(
            workspace_id=ws_id,
            name=name,
            status="active",
            currency="BRL",
            tags=[],
            metadata_json={},
            searchable_text=name.lower(),
            is_featured=False,
            sku=sku,
            external_id=external_id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def test_upsert_by_sku_updates_existing(self, db: Session):
        owner, ws = _setup(db)
        existing = self._make_existing(db, ws.id, "Old Name", sku="SKU-001")
        content = _csv_bytes([{"Nome": "New Name", "SKU": "SKU-001"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "sku": "SKU"},
                           mode="upsert_by_sku")
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == 1
        assert data["created"] == 0
        db.refresh(existing)
        assert existing.name == "New Name"

    def test_upsert_by_external_id_updates_existing(self, db: Session):
        owner, ws = _setup(db)
        existing = self._make_existing(db, ws.id, "Old", external_id="EXT-42")
        content = _csv_bytes([{"Nome": "Updated", "Codigo": "EXT-42"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome", "external_id": "Codigo"},
                           mode="upsert_by_external_id")
        assert resp.status_code == 200
        assert resp.json()["updated"] == 1
        db.refresh(existing)
        assert existing.name == "Updated"

    def test_upsert_by_sku_without_sku_mapping_returns_422(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "X"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome"}, mode="upsert_by_sku")
        assert resp.status_code == 422

    def test_upsert_by_external_id_without_mapping_returns_422(self, db: Session):
        owner, ws = _setup(db)
        content = _csv_bytes([{"Nome": "X"}])
        with _make_client(db, owner, ws) as client:
            resp = _commit(client, content, {"name": "Nome"}, mode="upsert_by_external_id")
        assert resp.status_code == 422

    def test_workspace_isolation_upsert_by_sku(self, db: Session):
        owner_a = _make_user(db, f"iso-a-{uuid.uuid4().hex[:4]}@t.com", "A")
        ws_a = _make_workspace(db, owner_a, f"iso-a-{uuid.uuid4().hex[:4]}", "WS A")
        owner_b = _make_user(db, f"iso-b-{uuid.uuid4().hex[:4]}@t.com", "B")
        ws_b = _make_workspace(db, owner_b, f"iso-b-{uuid.uuid4().hex[:4]}", "WS B")
        db.commit()

        item_a = self._make_existing(db, ws_a.id, "Item from A", sku="SHARED-SKU")

        content = _csv_bytes([{"Nome": "Item from B", "SKU": "SHARED-SKU"}])
        with _make_client(db, owner_b, ws_b) as client:
            resp = _commit(client, content, {"name": "Nome", "sku": "SKU"},
                           mode="upsert_by_sku")
        assert resp.status_code == 200

        db.refresh(item_a)
        assert item_a.name == "Item from A"  # unchanged
