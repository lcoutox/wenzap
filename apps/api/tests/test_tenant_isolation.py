"""
Tenant isolation tests.

Verifies that workspace A cannot access data from workspace B,
even when both are authenticated.
"""

from sqlalchemy.orm import Session

from app.models.workspace_member import WorkspaceMember


def test_workspace_a_cannot_see_workspace_b_members(client_a, workspace_b, user_b):
    """client_a is scoped to workspace_a — must not see workspace_b members."""
    response = client_a.get("/workspaces/current/members")
    assert response.status_code == 200
    members = response.json()
    emails = [m["email"] for m in members]
    assert user_b.email not in emails


def test_workspace_b_cannot_see_workspace_a_members(client_b, workspace_a, user_a):
    response = client_b.get("/workspaces/current/members")
    assert response.status_code == 200
    members = response.json()
    emails = [m["email"] for m in members]
    assert user_a.email not in emails


def test_workspace_a_cannot_patch_workspace_b(client_a, workspace_b):
    """Patching workspace should only affect the current authenticated workspace."""
    response = client_a.patch("/workspaces/current", json={"name": "Hacked"})
    assert response.status_code == 200
    # The returned workspace is workspace_a, not workspace_b
    assert response.json()["slug"] != workspace_b.slug


def test_workspace_a_cannot_change_workspace_b_member_role(
    client_a, db: Session, workspace_b, user_b
):
    """client_a must not be able to patch members in workspace_b."""
    member_b = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_b.id,
        WorkspaceMember.user_id == user_b.id,
    ).first()
    assert member_b is not None

    # client_a tries to patch member of workspace_b using its id
    response = client_a.patch(
        f"/workspaces/current/members/{member_b.id}/role", json={"role": "viewer"}
    )
    # Should return 404 because the member does not belong to workspace_a
    assert response.status_code == 404


def test_unauthenticated_request_blocked(unauthenticated_client):
    response = unauthenticated_client.get("/workspaces/current")
    assert response.status_code == 401
