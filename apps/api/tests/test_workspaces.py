from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import _make_workspace


def test_get_current_workspace(client_a: TestClient, workspace_a):
    response = client_a.get("/workspaces/current")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == workspace_a.slug
    assert data["name"] == workspace_a.name


def test_patch_workspace_name(client_a: TestClient):
    response = client_a.patch("/workspaces/current", json={"name": "New Name"})
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_patch_workspace_slug_conflict(client_a: TestClient, db: Session, user_b):
    _make_workspace(db, user_b, "workspace-b", "Workspace B")
    response = client_a.patch("/workspaces/current", json={"slug": "workspace-b"})
    assert response.status_code == 409


def test_patch_workspace_slug_invalid_format(client_a: TestClient):
    response = client_a.patch("/workspaces/current", json={"slug": "My Workspace!"})
    assert response.status_code == 422


def test_patch_workspace_slug_too_short(client_a: TestClient):
    response = client_a.patch("/workspaces/current", json={"slug": "ab"})
    assert response.status_code == 422


def test_patch_workspace_slug_valid(client_a: TestClient):
    response = client_a.patch("/workspaces/current", json={"slug": "my-workspace-123"})
    assert response.status_code == 200
    assert response.json()["slug"] == "my-workspace-123"
