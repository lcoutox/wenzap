
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client


def test_list_members(client_a: TestClient, user_a):
    response = client_a.get("/workspaces/current/members")
    assert response.status_code == 200
    members = response.json()
    assert len(members) >= 1
    emails = [m["email"] for m in members]
    assert user_a.email in emails


def test_member_role_visible(client_a: TestClient, user_a):
    response = client_a.get("/workspaces/current/members")
    members = response.json()
    owner = next(m for m in members if m["email"] == user_a.email)
    assert owner["role"] == "owner"


def test_owner_can_change_member_role(client_a: TestClient, db: Session, workspace_a, user_b):
    m = WorkspaceMember(
        workspace_id=workspace_a.id,
        user_id=user_b.id,
        role=MemberRole.member,
        status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    response = client_a.patch(
        f"/workspaces/current/members/{m.id}/role", json={"role": "admin"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_non_owner_cannot_change_role(db: Session, workspace_b, user_a, user_b):
    """A member (not owner) cannot change roles — uses a dedicated client for user_a as member."""
    m = WorkspaceMember(
        workspace_id=workspace_b.id,
        user_id=user_a.id,
        role=MemberRole.member,
        status=MemberStatus.active,
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    # Build a client scoped to workspace_b but authenticated as user_a (member, not owner)
    with _make_client(db, user_a, workspace_b) as client:
        response = client.patch(
            f"/workspaces/current/members/{m.id}/role", json={"role": "admin"}
        )
    assert response.status_code == 403
