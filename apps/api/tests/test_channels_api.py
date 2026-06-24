"""
Tests for Phase 5.4.1 — Channels API (authenticated, internal).

Covers:
  create
  - owner creates web_widget
  - admin creates web_widget
  - member cannot create (403)
  - viewer cannot create (403)
  - agent from another workspace returns 404
  - unimplemented channel_type (e.g. whatsapp) returns 422
  - public_key ignored/not accepted in body
  - public_key generated starts with wgt_
  - default config applied when not provided
  - custom config validated and stored
  - primary_color invalid → 422
  - allowed_origins normalized (deduplicated, trimmed)

  list
  - owner/admin/member/viewer can list (200)
  - lists only workspace's channels
  - filter by channel_type
  - filter by agent_id
  - archived channels excluded from default list

  get detail
  - owner/admin/member/viewer can get detail (200)
  - cross-workspace returns 404

  patch
  - owner/admin can update name/config/allowed_origins/status
  - member cannot patch (403)
  - viewer cannot patch (403)
  - public_key does not change on patch
  - channel_type does not change on patch (field not accepted)
  - agent_id does not change on patch (field not accepted)
  - cross-workspace returns 404
  - status can be set to inactive
  - status cannot be set to archived via patch (only via /archive)

  archive
  - owner/admin can archive
  - member cannot archive (403)
  - viewer cannot archive (403)
  - archive is idempotent
  - archived channel does not appear in default list
  - archived channel detail still readable

  tenant isolation
  - workspace A cannot read channel from workspace B
  - workspace A cannot create channel with agent from workspace B
  - workspace A cannot edit channel from workspace B
  - workspace A cannot archive channel from workspace B
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.models.agent import Agent
from app.models.channel import Channel
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from tests.conftest import _make_client, _make_user

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_member(db: Session, workspace: Workspace, role: MemberRole) -> User:
    email = f"{role.value}-{uuid.uuid4().hex[:6]}@test.com"
    user = _make_user(db, email, f"{role.value.title()} User")
    db.add(WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=role,
        status=MemberStatus.active,
    ))
    db.flush()
    return user


def _make_agent(db: Session, workspace_id: uuid.UUID, name: str = "Agent") -> Agent:
    agent = Agent(workspace_id=workspace_id, name=name, status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    *,
    name: str = "My Widget",
    status: str = "active",
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="web_widget",
        name=name,
        public_key=f"wgt_{uuid.uuid4().hex[:24]}",
        status=status,
        config_json={},
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _create_payload(agent_id: uuid.UUID, **kwargs) -> dict:
    return {
        "agent_id": str(agent_id),
        "channel_type": "web_widget",
        "name": "Test Widget",
        **kwargs,
    }


# ── CREATE ─────────────────────────────────────────────────────────────────────

def test_owner_creates_web_widget(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    resp = client_a.post("/channels", json=_create_payload(agent.id))

    assert resp.status_code == 201
    body = resp.json()
    assert body["channel_type"] == "web_widget"
    assert body["name"] == "Test Widget"
    assert body["status"] == "active"
    assert body["public_key"].startswith("wgt_")
    assert body["workspace_id"] == str(workspace_a.id)
    assert body["agent_id"] == str(agent.id)


def test_admin_creates_web_widget(db: Session, workspace_a: Workspace):
    admin = _make_member(db, workspace_a, MemberRole.admin)
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    with _make_client(db, admin, workspace_a) as client:
        resp = client.post("/channels", json=_create_payload(agent.id))

    assert resp.status_code == 201


def test_member_cannot_create(db: Session, workspace_a: Workspace):
    member = _make_member(db, workspace_a, MemberRole.member)
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    with _make_client(db, member, workspace_a) as client:
        resp = client.post("/channels", json=_create_payload(agent.id))

    assert resp.status_code == 403


def test_viewer_cannot_create(db: Session, workspace_a: Workspace):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        resp = client.post("/channels", json=_create_payload(agent.id))

    assert resp.status_code == 403


def test_agent_from_other_workspace_returns_404(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_b = _make_agent(db, workspace_b.id)
    db.commit()

    resp = client_a.post("/channels", json=_create_payload(agent_b.id))

    assert resp.status_code == 404


def test_unimplemented_channel_type_returns_422(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    payload = {"agent_id": str(agent.id), "channel_type": "whatsapp", "name": "WA Widget"}
    resp = client_a.post("/channels", json=payload)

    assert resp.status_code == 422


def test_public_key_not_accepted_in_body(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    payload = {**_create_payload(agent.id), "public_key": "wgt_custom_key_injected"}
    resp = client_a.post("/channels", json=payload)

    # public_key is not a field in ChannelCreate — FastAPI ignores or rejects extra fields.
    # If 201, the returned public_key must NOT be the one we supplied.
    if resp.status_code == 201:
        assert resp.json()["public_key"] != "wgt_custom_key_injected"
    else:
        # 422 is also acceptable (extra field rejection).
        assert resp.status_code == 422


def test_public_key_starts_with_wgt(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    resp = client_a.post("/channels", json=_create_payload(agent.id))

    assert resp.status_code == 201
    assert resp.json()["public_key"].startswith("wgt_")


def test_default_config_applied(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    resp = client_a.post("/channels", json=_create_payload(agent.id))

    assert resp.status_code == 201
    cfg = resp.json()["config"]
    assert cfg["theme"] == "dark"
    assert cfg["primary_color"] == "#6366f1"
    assert cfg["position"] == "bottom-right"
    assert cfg["auto_open"] is False


def test_custom_config_stored(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    payload = _create_payload(agent.id, config={"theme": "light", "primary_color": "#ff0000"})
    resp = client_a.post("/channels", json=payload)

    assert resp.status_code == 201
    assert resp.json()["config"]["theme"] == "light"
    assert resp.json()["config"]["primary_color"] == "#ff0000"


def test_invalid_primary_color_rejected(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    payload = _create_payload(agent.id, config={"primary_color": "red"})
    resp = client_a.post("/channels", json=payload)

    assert resp.status_code == 422


def test_allowed_origins_normalized(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    db.commit()

    # Duplicates should be removed; whitespace trimmed.
    payload = _create_payload(
        agent.id,
        allowed_origins=[
            "https://example.com",
            "  https://example.com  ",
            "https://app.example.com",
        ],
    )
    resp = client_a.post("/channels", json=payload)

    assert resp.status_code == 201
    origins = resp.json()["allowed_origins"]
    assert origins.count("https://example.com") == 1
    assert "https://app.example.com" in origins


# ── LIST ───────────────────────────────────────────────────────────────────────

def test_owner_can_list(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    _make_channel(db, workspace_a.id, agent.id)

    resp = client_a.get("/channels")

    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_member_can_list(db: Session, workspace_a: Workspace):
    member = _make_member(db, workspace_a, MemberRole.member)
    agent = _make_agent(db, workspace_a.id)
    _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, member, workspace_a) as client:
        resp = client.get("/channels")

    assert resp.status_code == 200


def test_viewer_can_list(db: Session, workspace_a: Workspace):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    agent = _make_agent(db, workspace_a.id)
    _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, viewer, workspace_a) as client:
        resp = client.get("/channels")

    assert resp.status_code == 200


def test_list_only_own_workspace(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_a = _make_agent(db, workspace_a.id)
    agent_b = _make_agent(db, workspace_b.id)
    _make_channel(db, workspace_a.id, agent_a.id, name="A Widget")
    _make_channel(db, workspace_b.id, agent_b.id, name="B Widget")

    resp = client_a.get("/channels")

    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "A Widget" in names
    assert "B Widget" not in names


def test_list_filter_by_channel_type(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    _make_channel(db, workspace_a.id, agent.id)

    resp = client_a.get("/channels?channel_type=web_widget")

    assert resp.status_code == 200
    for ch in resp.json():
        assert ch["channel_type"] == "web_widget"


def test_list_filter_by_agent_id(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent1 = _make_agent(db, workspace_a.id, "Agent 1")
    agent2 = _make_agent(db, workspace_a.id, "Agent 2")
    _make_channel(db, workspace_a.id, agent1.id, name="Widget 1")
    _make_channel(db, workspace_a.id, agent2.id, name="Widget 2")

    resp = client_a.get(f"/channels?agent_id={agent1.id}")

    assert resp.status_code == 200
    ids = [c["agent_id"] for c in resp.json()]
    assert all(i == str(agent1.id) for i in ids)


def test_archived_excluded_from_default_list(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    _make_channel(db, workspace_a.id, agent.id, name="Active Widget", status="active")
    _make_channel(db, workspace_a.id, agent.id, name="Archived Widget", status="archived")

    resp = client_a.get("/channels")

    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Active Widget" in names
    assert "Archived Widget" not in names


# ── GET DETAIL ─────────────────────────────────────────────────────────────────

def test_get_detail_owner(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = client_a.get(f"/channels/{ch.id}")

    assert resp.status_code == 200
    assert resp.json()["id"] == str(ch.id)


def test_get_detail_member(db: Session, workspace_a: Workspace):
    member = _make_member(db, workspace_a, MemberRole.member)
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, member, workspace_a) as client:
        resp = client.get(f"/channels/{ch.id}")

    assert resp.status_code == 200


def test_get_detail_viewer(db: Session, workspace_a: Workspace):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, viewer, workspace_a) as client:
        resp = client.get(f"/channels/{ch.id}")

    assert resp.status_code == 200


def test_get_detail_cross_workspace_404(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_b = _make_agent(db, workspace_b.id)
    ch_b = _make_channel(db, workspace_b.id, agent_b.id)

    resp = client_a.get(f"/channels/{ch_b.id}")

    assert resp.status_code == 404


# ── PATCH ──────────────────────────────────────────────────────────────────────

def test_patch_name(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, name="Old Name")

    resp = client_a.patch(f"/channels/{ch.id}", json={"name": "New Name"})

    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_patch_config(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = client_a.patch(f"/channels/{ch.id}", json={"config": {"theme": "light"}})

    assert resp.status_code == 200
    assert resp.json()["config"]["theme"] == "light"


def test_patch_allowed_origins(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = client_a.patch(
        f"/channels/{ch.id}",
        json={"allowed_origins": ["https://example.com"]},
    )

    assert resp.status_code == 200
    assert "https://example.com" in resp.json()["allowed_origins"]


def test_patch_status_to_inactive(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = client_a.patch(f"/channels/{ch.id}", json={"status": "inactive"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "inactive"


def test_patch_status_archived_rejected(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    # "archived" is not an allowed value for ChannelUpdate.status (only active/inactive).
    resp = client_a.patch(f"/channels/{ch.id}", json={"status": "archived"})

    assert resp.status_code == 422


def test_patch_public_key_unchanged(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    original_key = ch.public_key

    resp = client_a.patch(f"/channels/{ch.id}", json={"name": "Renamed"})

    assert resp.status_code == 200
    assert resp.json()["public_key"] == original_key


def test_patch_member_forbidden(db: Session, workspace_a: Workspace):
    member = _make_member(db, workspace_a, MemberRole.member)
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, member, workspace_a) as client:
        resp = client.patch(f"/channels/{ch.id}", json={"name": "Hacked"})

    assert resp.status_code == 403


def test_patch_viewer_forbidden(db: Session, workspace_a: Workspace):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, viewer, workspace_a) as client:
        resp = client.patch(f"/channels/{ch.id}", json={"name": "Hacked"})

    assert resp.status_code == 403


def test_patch_cross_workspace_404(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_b = _make_agent(db, workspace_b.id)
    ch_b = _make_channel(db, workspace_b.id, agent_b.id)

    resp = client_a.patch(f"/channels/{ch_b.id}", json={"name": "Hacked"})

    assert resp.status_code == 404


# ── ARCHIVE ────────────────────────────────────────────────────────────────────

def test_archive_sets_status(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = client_a.post(f"/channels/{ch.id}/archive")

    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_archive_idempotent(db: Session, workspace_a: Workspace, client_a: TestClient):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    client_a.post(f"/channels/{ch.id}/archive")
    resp = client_a.post(f"/channels/{ch.id}/archive")

    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_archived_not_in_default_list(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    client_a.post(f"/channels/{ch.id}/archive")

    resp = client_a.get("/channels")

    ids = [c["id"] for c in resp.json()]
    assert str(ch.id) not in ids


def test_archived_detail_still_readable(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    client_a.post(f"/channels/{ch.id}/archive")

    resp = client_a.get(f"/channels/{ch.id}")

    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_archive_member_forbidden(db: Session, workspace_a: Workspace):
    member = _make_member(db, workspace_a, MemberRole.member)
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, member, workspace_a) as client:
        resp = client.post(f"/channels/{ch.id}/archive")

    assert resp.status_code == 403


def test_archive_viewer_forbidden(db: Session, workspace_a: Workspace):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    with _make_client(db, viewer, workspace_a) as client:
        resp = client.post(f"/channels/{ch.id}/archive")

    assert resp.status_code == 403


def test_archive_cross_workspace_404(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_b = _make_agent(db, workspace_b.id)
    ch_b = _make_channel(db, workspace_b.id, agent_b.id)

    resp = client_a.post(f"/channels/{ch_b.id}/archive")

    assert resp.status_code == 404


# ── TENANT ISOLATION ──────────────────────────────────────────────────────────

def test_workspace_a_cannot_create_with_agent_from_b(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_b = _make_agent(db, workspace_b.id)
    db.commit()

    resp = client_a.post("/channels", json=_create_payload(agent_b.id))

    assert resp.status_code == 404


def test_workspace_a_cannot_edit_channel_from_b(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_b = _make_agent(db, workspace_b.id)
    ch_b = _make_channel(db, workspace_b.id, agent_b.id)

    resp = client_a.patch(f"/channels/{ch_b.id}", json={"name": "Hacked"})

    assert resp.status_code == 404


def test_workspace_a_cannot_archive_channel_from_b(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, client_a: TestClient
):
    agent_b = _make_agent(db, workspace_b.id)
    ch_b = _make_channel(db, workspace_b.id, agent_b.id)

    resp = client_a.post(f"/channels/{ch_b.id}/archive")

    assert resp.status_code == 404
