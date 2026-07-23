"""
Tests for /workspaces/current/integrations — whatsapp-voice-groq-elevenlabs-prd.md.

Covers:
- GET returns groq_configured/elevenlabs_configured=False by default
- PUT stores a key and flips the corresponding *_configured flag
- PUT never echoes the plaintext key back
- PUT validates the provider path param (only groq/elevenlabs)
- PUT rejects an empty api_key
- DELETE removes a configured key
- Only owner/admin can read or write (member/viewer get 403)
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client, _make_user


def _make_member_with_role(db: Session, workspace: Workspace, role: MemberRole) -> object:
    u = _make_user(db, f"u{uuid.uuid4().hex[:6]}@t.com", "Member")
    m = WorkspaceMember(
        workspace_id=workspace.id, user_id=u.id, role=role, status=MemberStatus.active
    )
    db.add(m)
    db.commit()
    return u


def test_get_integrations_defaults_to_unconfigured(client_a: TestClient):
    response = client_a.get("/workspaces/current/integrations")
    assert response.status_code == 200
    assert response.json() == {"groq_configured": False, "elevenlabs_configured": False}


def test_put_groq_key_flips_configured_flag(client_a: TestClient):
    response = client_a.put(
        "/workspaces/current/integrations/groq", json={"api_key": "gsk-my-real-key"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["groq_configured"] is True
    assert body["elevenlabs_configured"] is False
    assert "gsk-my-real-key" not in response.text


def test_put_elevenlabs_key_flips_configured_flag(client_a: TestClient):
    response = client_a.put(
        "/workspaces/current/integrations/elevenlabs", json={"api_key": "el-my-real-key"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["elevenlabs_configured"] is True
    assert body["groq_configured"] is False


def test_put_invalid_provider_returns_422(client_a: TestClient):
    response = client_a.put(
        "/workspaces/current/integrations/openai", json={"api_key": "some-key"}
    )
    assert response.status_code == 422


def test_put_empty_api_key_returns_422(client_a: TestClient):
    response = client_a.put("/workspaces/current/integrations/groq", json={"api_key": ""})
    assert response.status_code == 422


def test_delete_removes_configured_key(client_a: TestClient):
    client_a.put("/workspaces/current/integrations/groq", json={"api_key": "gsk-my-real-key"})

    response = client_a.delete("/workspaces/current/integrations/groq")
    assert response.status_code == 204

    after = client_a.get("/workspaces/current/integrations")
    assert after.json()["groq_configured"] is False


def test_member_cannot_read_integrations(db: Session, workspace_a: Workspace):
    member = _make_member_with_role(db, workspace_a, MemberRole.member)
    with _make_client(db, member, workspace_a) as client:
        response = client.get("/workspaces/current/integrations")
    assert response.status_code == 403


def test_viewer_cannot_write_integrations(db: Session, workspace_a: Workspace):
    viewer = _make_member_with_role(db, workspace_a, MemberRole.viewer)
    with _make_client(db, viewer, workspace_a) as client:
        response = client.put(
            "/workspaces/current/integrations/groq", json={"api_key": "gsk-x"}
        )
    assert response.status_code == 403


def test_admin_can_write_integrations(db: Session, workspace_a: Workspace):
    admin = _make_member_with_role(db, workspace_a, MemberRole.admin)
    with _make_client(db, admin, workspace_a) as client:
        response = client.put(
            "/workspaces/current/integrations/groq", json={"api_key": "gsk-x"}
        )
    assert response.status_code == 200
    assert response.json()["groq_configured"] is True
