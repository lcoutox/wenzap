"""
Tests for Phase 6.1-A — WhatsApp Channel API.

Covers:
  create
  - owner creates whatsapp channel (201)
  - admin creates whatsapp channel (201)
  - member cannot create (403)
  - viewer cannot create (403)
  - agent from another workspace rejected (404)
  - public_key starts with wap_
  - web_widget public_key still starts with wgt_
  - config stored without access_token_ref in ChannelOut (only the ref, not token)
  - archived whatsapp channel excluded from default list

  list / detail / patch
  - list includes whatsapp channel
  - detail returns config without real token
  - patch updates whatsapp config (phone_number_id, display_phone_number)
  - patch with web_widget config on whatsapp channel rejected

  lookup
  - get_whatsapp_channel_by_phone_number_id returns correct channel
  - unknown phone_number_id returns None
  - archived channel not returned
  - web_widget channel not returned even if config_json has matching value
  - two workspaces: returns channel by phone_number_id regardless of workspace
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
from app.services.channel_service import get_whatsapp_channel_by_phone_number_id
from app.models.workspace_subscription import WorkspaceSubscription
from tests.conftest import _make_client, _make_user

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_member(db: Session, workspace: Workspace, role: MemberRole) -> User:
    email = f"{role.value}-{uuid.uuid4().hex[:6]}@wap-test.com"
    user = _make_user(db, email, f"{role.value.title()} User")
    db.add(WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=role,
        status=MemberStatus.active,
    ))
    db.flush()
    return user


def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="WA Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _whatsapp_payload(agent_id: uuid.UUID, phone_number_id: str = "111222333") -> dict:
    return {
        "agent_id": str(agent_id),
        "channel_type": "whatsapp",
        "name": "WhatsApp Principal",
        "config": {
            "waba_id": "9999000011112222",
            "phone_number_id": phone_number_id,
            "display_phone_number": "+55 11 99999-9999",
        },
    }


def _make_whatsapp_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    phone_number_id: str = "111222333",
    status: str = "active",
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type="whatsapp",
        name="WhatsApp Test",
        public_key=f"wap_{uuid.uuid4().hex[:24]}",
        status=status,
        config_json={
            "provider": "meta_cloud_api",
            "onboarding_type": "manual",
            "waba_id": "9999000011112222",
            "phone_number_id": phone_number_id,
            "display_phone_number": None,
            "business_id": None,
            "access_token_ref": None,
            "status": "testing",
            "connected_at": None,
            "last_webhook_at": None,
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


# ── CREATE ─────────────────────────────────────────────────────────────────────


def test_owner_creates_whatsapp_channel(
    db: Session, workspace_a: Workspace, client_a: TestClient, growth_subscription_a: WorkspaceSubscription
):
    agent = _make_agent(db, workspace_a.id)
    resp = client_a.post("/channels", json=_whatsapp_payload(agent.id))
    assert resp.status_code == 201
    data = resp.json()
    assert data["channel_type"] == "whatsapp"
    assert data["config"]["waba_id"] == "9999000011112222"


def test_admin_creates_whatsapp_channel(
    db: Session, workspace_a: Workspace, client_a: TestClient, growth_subscription_a: WorkspaceSubscription
):
    admin = _make_member(db, workspace_a, MemberRole.admin)
    agent = _make_agent(db, workspace_a.id)
    with _make_client(db, admin, workspace_a) as client:
        resp = client.post("/channels", json=_whatsapp_payload(agent.id))
    assert resp.status_code == 201


def test_member_cannot_create_whatsapp_channel(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    member = _make_member(db, workspace_a, MemberRole.member)
    agent = _make_agent(db, workspace_a.id)
    with _make_client(db, member, workspace_a) as client:
        resp = client.post("/channels", json=_whatsapp_payload(agent.id))
    assert resp.status_code == 403


def test_viewer_cannot_create_whatsapp_channel(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    agent = _make_agent(db, workspace_a.id)
    with _make_client(db, viewer, workspace_a) as client:
        resp = client.post("/channels", json=_whatsapp_payload(agent.id))
    assert resp.status_code == 403


def test_agent_from_other_workspace_rejected(
    db: Session,
    workspace_a: Workspace,
    workspace_b: Workspace,
    client_a: TestClient,
    growth_subscription_a: WorkspaceSubscription,
):
    agent_b = _make_agent(db, workspace_b.id)
    resp = client_a.post("/channels", json=_whatsapp_payload(agent_b.id))
    assert resp.status_code == 404


def test_whatsapp_public_key_starts_with_wap(
    db: Session, workspace_a: Workspace, client_a: TestClient, growth_subscription_a: WorkspaceSubscription
):
    agent = _make_agent(db, workspace_a.id)
    resp = client_a.post("/channels", json=_whatsapp_payload(agent.id))
    assert resp.status_code == 201
    assert resp.json()["public_key"].startswith("wap_")


def test_web_widget_public_key_still_starts_with_wgt(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    resp = client_a.post("/channels", json={
        "agent_id": str(agent.id),
        "channel_type": "web_widget",
        "name": "Widget Test",
    })
    assert resp.status_code == 201
    assert resp.json()["public_key"].startswith("wgt_")


def test_channel_out_does_not_expose_raw_token(
    db: Session, workspace_a: Workspace, client_a: TestClient, growth_subscription_a: WorkspaceSubscription
):
    """access_token_ref is a reference string, never a real token."""
    agent = _make_agent(db, workspace_a.id)
    payload = _whatsapp_payload(agent.id)
    payload["config"]["access_token_ref"] = "env:WHATSAPP_TEMP_ACCESS_TOKEN"
    resp = client_a.post("/channels", json=payload)
    assert resp.status_code == 201
    config = resp.json()["config"]
    # The ref string itself is fine to return; what matters is it's not a real token
    assert config.get("access_token_ref") == "env:WHATSAPP_TEMP_ACCESS_TOKEN"
    # Sanity: no key named "access_token" (the actual token) should exist
    assert "access_token" not in config


# ── LIST / DETAIL ──────────────────────────────────────────────────────────────


def test_list_includes_whatsapp_channel(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="444555666")
    resp = client_a.get("/channels")
    assert resp.status_code == 200
    types = [c["channel_type"] for c in resp.json()]
    assert "whatsapp" in types


def test_detail_returns_whatsapp_config(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="555666777")
    resp = client_a.get(f"/channels/{ch.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["channel_type"] == "whatsapp"
    assert data["config"]["phone_number_id"] == "555666777"


def test_archived_whatsapp_not_in_default_list(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_whatsapp_channel(
        db, workspace_a.id, agent.id, phone_number_id="999888777", status="archived"
    )
    resp = client_a.get("/channels")
    ids = [c["id"] for c in resp.json()]
    assert str(ch.id) not in ids


# ── PATCH ──────────────────────────────────────────────────────────────────────


def test_patch_updates_whatsapp_config(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="111000111")
    resp = client_a.patch(f"/channels/{ch.id}", json={
        "config": {
            "waba_id": "9999000011112222",
            "phone_number_id": "111000111",
            "display_phone_number": "+55 21 91111-0000",
        },
    })
    assert resp.status_code == 200
    assert resp.json()["config"]["display_phone_number"] == "+55 21 91111-0000"


def test_patch_whatsapp_channel_with_connected_at_set_does_not_500(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    """Regression: updating a channel whose config already has connected_at set
    (any WhatsApp channel post-connection) used to 500 with "Object of type
    datetime is not JSON serializable" — Pydantic parses the stored ISO string
    into a real datetime on validation, and model_dump() (default mode="python")
    left it as a live datetime object that JSONB can't encode. Fixed via
    model_dump(mode="json") in schemas/channel.py::_parse_whatsapp_config.
    """
    agent = _make_agent(db, workspace_a.id)
    ch = _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="333444555")
    ch.config_json = {**ch.config_json, "connected_at": "2026-07-14T00:16:31.174502+00:00"}
    db.commit()

    resp = client_a.patch(f"/channels/{ch.id}", json={
        "config": {**ch.config_json, "auto_reply_enabled": True},
    })
    assert resp.status_code == 200
    assert resp.json()["config"]["auto_reply_enabled"] is True
    assert resp.json()["config"]["connected_at"] == "2026-07-14T00:16:31.174502Z"


def test_patch_evolution_whatsapp_channel_with_connected_at_set_does_not_500(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    """Same regression as above, for the evolution_api provider config."""
    agent = _make_agent(db, workspace_a.id)
    ch = Channel(
        workspace_id=workspace_a.id, agent_id=agent.id, channel_type="whatsapp",
        name="Evolution Test", public_key=f"wap_{uuid.uuid4().hex[:24]}", status="active",
        config_json={
            "provider": "evolution_api", "onboarding_type": "qr_code",
            "base_url": "https://nexevolution.up.railway.app",
            "instance_name": "wenzap-regression-test", "display_phone_number": None,
            "api_key_ref": "db:00000000-0000-0000-0000-000000000000",
            "status": "active", "connected_at": "2026-07-14T00:16:31.174502+00:00",
            "last_webhook_at": None, "auto_reply_enabled": False,
        },
        allowed_origins=[],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)

    resp = client_a.patch(f"/channels/{ch.id}", json={
        "config": {**ch.config_json, "auto_reply_enabled": True},
    })
    assert resp.status_code == 200
    assert resp.json()["config"]["auto_reply_enabled"] is True
    assert resp.json()["config"]["provider"] == "evolution_api"


def test_patch_whatsapp_channel_with_web_widget_config_rejected(
    db: Session, workspace_a: Workspace, client_a: TestClient
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="222333444")
    resp = client_a.patch(f"/channels/{ch.id}", json={
        "config": {"theme": "dark", "primary_color": "#6366f1"},
    })
    # WebWidgetConfig fields are not valid for whatsapp (extra="forbid")
    assert resp.status_code == 422


# ── LOOKUP ─────────────────────────────────────────────────────────────────────


class TestGetWhatsappChannelByPhoneNumberId:
    def test_known_phone_number_id_returns_channel(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        ch = _make_whatsapp_channel(db, workspace_a.id, agent.id, phone_number_id="LOOKUP_001")
        result = get_whatsapp_channel_by_phone_number_id(db, "LOOKUP_001")
        assert result is not None
        assert result.id == ch.id
        assert result.workspace_id == workspace_a.id

    def test_unknown_phone_number_id_returns_none(
        self, db: Session, workspace_a: Workspace
    ):
        result = get_whatsapp_channel_by_phone_number_id(db, "NONEXISTENT_ID")
        assert result is None

    def test_archived_channel_not_returned(
        self, db: Session, workspace_a: Workspace
    ):
        agent = _make_agent(db, workspace_a.id)
        _make_whatsapp_channel(
            db, workspace_a.id, agent.id, phone_number_id="LOOKUP_ARCH", status="archived"
        )
        result = get_whatsapp_channel_by_phone_number_id(db, "LOOKUP_ARCH")
        assert result is None

    def test_web_widget_not_returned_even_with_matching_config_key(
        self, db: Session, workspace_a: Workspace
    ):
        """A web_widget channel with phone_number_id in its config_json must not match."""
        agent = _make_agent(db, workspace_a.id)
        ch = Channel(
            workspace_id=workspace_a.id,
            agent_id=agent.id,
            channel_type="web_widget",
            name="Widget",
            public_key=f"wgt_{uuid.uuid4().hex[:24]}",
            status="active",
            config_json={"phone_number_id": "LOOKUP_WGT"},
            allowed_origins=[],
        )
        db.add(ch)
        db.commit()
        result = get_whatsapp_channel_by_phone_number_id(db, "LOOKUP_WGT")
        assert result is None

    def test_two_workspaces_returns_correct_channel(
        self,
        db: Session,
        workspace_a: Workspace,
        workspace_b: Workspace,
    ):
        agent_a = _make_agent(db, workspace_a.id)
        agent_b = _make_agent(db, workspace_b.id)
        ch_a = _make_whatsapp_channel(db, workspace_a.id, agent_a.id, phone_number_id="LOOKUP_WS_A")
        ch_b = _make_whatsapp_channel(db, workspace_b.id, agent_b.id, phone_number_id="LOOKUP_WS_B")

        res_a = get_whatsapp_channel_by_phone_number_id(db, "LOOKUP_WS_A")
        res_b = get_whatsapp_channel_by_phone_number_id(db, "LOOKUP_WS_B")

        assert res_a is not None and res_a.id == ch_a.id
        assert res_b is not None and res_b.id == ch_b.id
        assert res_a.workspace_id == workspace_a.id
        assert res_b.workspace_id == workspace_b.id
