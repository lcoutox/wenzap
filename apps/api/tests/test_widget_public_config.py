"""
Tests for Phase 5.4.2 — GET /public/widgets/{public_key}/config

Covers:
  - returns public config for active web_widget channel
  - does NOT return workspace_id
  - does NOT return agent_id
  - does NOT return allowed_origins
  - does NOT return internal channel id
  - inactive channel returns 404
  - archived channel returns 404
  - unknown public_key returns 404
  - channel_type != web_widget (inserted directly) returns 404
  - origin in allowed_origins → 200
  - origin NOT in allowed_origins → 403
  - allowed_origins empty → any origin allowed
  - allowed_origins non-empty + Origin header absent → 403
  - config defaults applied when config_json is empty
  - custom config fields returned correctly
"""

import uuid

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.workspace import Workspace

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    *,
    channel_type: str = "web_widget",
    status: str = "active",
    config_json: dict | None = None,
    allowed_origins: list[str] | None = None,
) -> Channel:
    ch = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type=channel_type,
        name="Test Widget",
        public_key=f"wgt_{uuid.uuid4().hex[:24]}",
        status=status,
        config_json=config_json if config_json is not None else {},
        allowed_origins=allowed_origins if allowed_origins is not None else [],
    )
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def _get_config(client, public_key: str, origin: str | None = None):
    headers = {"Origin": origin} if origin else {}
    return client.get(f"/public/widgets/{public_key}/config", headers=headers)


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_returns_config_for_active_widget(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _get_config(public_client, ch.public_key)

    assert resp.status_code == 200
    body = resp.json()
    assert body["public_key"] == ch.public_key
    assert body["name"] == "Test Widget"


def test_does_not_expose_workspace_id(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _get_config(public_client, ch.public_key)

    assert "workspace_id" not in resp.json()


def test_does_not_expose_agent_id(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _get_config(public_client, ch.public_key)

    assert "agent_id" not in resp.json()


def test_does_not_expose_allowed_origins(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id,
        allowed_origins=["https://example.com"],
    )

    resp = _get_config(public_client, ch.public_key)

    assert "allowed_origins" not in resp.json()


def test_does_not_expose_internal_channel_id(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _get_config(public_client, ch.public_key)

    assert "id" not in resp.json()


def test_inactive_channel_returns_404(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, status="inactive")

    resp = _get_config(public_client, ch.public_key)

    assert resp.status_code == 404


def test_archived_channel_returns_404(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, status="archived")

    resp = _get_config(public_client, ch.public_key)

    assert resp.status_code == 404


def test_unknown_public_key_returns_404(
    db: Session, workspace_a: Workspace, public_client
):
    resp = _get_config(public_client, "wgt_nonexistentkey0000000")

    assert resp.status_code == 404


def test_non_web_widget_channel_type_returns_404(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    # Insert a non-web_widget channel directly, bypassing service validation.
    ch = _make_channel(db, workspace_a.id, agent.id, channel_type="api")

    resp = _get_config(public_client, ch.public_key)

    assert resp.status_code == 404


def test_origin_in_allowed_list_permitted(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id,
        allowed_origins=["https://example.com", "https://other.com"],
    )

    resp = _get_config(public_client, ch.public_key, origin="https://example.com")

    assert resp.status_code == 200


def test_origin_not_in_allowed_list_forbidden(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id,
        allowed_origins=["https://example.com"],
    )

    resp = _get_config(public_client, ch.public_key, origin="https://evil.com")

    assert resp.status_code == 403


def test_empty_allowed_origins_permits_any_origin(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, allowed_origins=[])

    resp = _get_config(public_client, ch.public_key, origin="https://anything.com")

    assert resp.status_code == 200


def test_empty_allowed_origins_permits_absent_origin(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, allowed_origins=[])

    resp = _get_config(public_client, ch.public_key)  # no Origin header

    assert resp.status_code == 200


def test_non_empty_allowed_origins_absent_origin_forbidden(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id,
        allowed_origins=["https://example.com"],
    )

    resp = _get_config(public_client, ch.public_key)  # no Origin header

    assert resp.status_code == 403


def test_default_config_applied_when_config_json_empty(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id, config_json={})

    resp = _get_config(public_client, ch.public_key)

    body = resp.json()
    assert body["theme"] == "dark"
    assert body["primary_color"] == "#6366f1"
    assert body["position"] == "bottom-right"
    assert body["auto_open"] is False
    assert body["auto_open_delay_seconds"] == 3


def test_custom_config_returned_correctly(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id,
        config_json={
            "theme": "light",
            "primary_color": "#ff0000",
            "welcome_message": "Bem-vindo!",
            "auto_open": True,
            "auto_open_delay_seconds": 5,
        },
    )

    resp = _get_config(public_client, ch.public_key)

    body = resp.json()
    assert body["theme"] == "light"
    assert body["primary_color"] == "#ff0000"
    assert body["welcome_message"] == "Bem-vindo!"
    assert body["auto_open"] is True
    assert body["auto_open_delay_seconds"] == 5
