from fastapi.testclient import TestClient


def test_me_without_token_returns_401(unauthenticated_client: TestClient):
    response = unauthenticated_client.get("/me")
    assert response.status_code == 401


def test_me_with_invalid_token_returns_401(unauthenticated_client: TestClient):
    response = unauthenticated_client.get("/me", headers={"Authorization": "Bearer invalid.token"})
    assert response.status_code == 401


def test_me_returns_user_and_workspace(client_a, user_a, workspace_a):
    response = client_a.get("/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_a.email
    assert data["workspace"]["slug"] == workspace_a.slug
    assert data["role"] == "owner"
