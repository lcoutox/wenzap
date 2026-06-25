"""
Tests for Phase 5.6 — Visitor Identity & Lead Capture.

Covers:
- WebWidgetConfig validation (capture settings)
- GET /config returns capture fields
- POST /sessions returns contact_captured flag
- PATCH /session/contact — field updates, validation, security
- POST /messages blocked when capture required but incomplete
"""


import pytest
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.workspace import Workspace
from app.schemas.channel import WebWidgetConfig
from tests.test_widget_messages import _make_agent_simple, _make_channel, _make_session

# ── WebWidgetConfig validation ────────────────────────────────────────────────

def test_config_capture_disabled_is_valid():
    cfg = WebWidgetConfig(contact_capture_enabled=False)
    assert cfg.contact_capture_enabled is False


def test_config_capture_enabled_with_name():
    cfg = WebWidgetConfig(contact_capture_enabled=True, require_name=True)
    assert cfg.require_name is True


def test_config_capture_enabled_with_email():
    cfg = WebWidgetConfig(contact_capture_enabled=True, require_email=True)
    assert cfg.require_email is True


def test_config_capture_enabled_with_phone():
    cfg = WebWidgetConfig(contact_capture_enabled=True, require_phone=True)
    assert cfg.require_phone is True


def test_config_capture_enabled_all_fields():
    cfg = WebWidgetConfig(
        contact_capture_enabled=True,
        require_name=True,
        require_email=True,
        require_phone=True,
    )
    assert cfg.require_name and cfg.require_email and cfg.require_phone


def test_config_capture_enabled_no_fields_raises():
    with pytest.raises(Exception, match="at least one"):
        WebWidgetConfig(contact_capture_enabled=True)


# ── GET /config returns capture fields ────────────────────────────────────────

def test_get_config_returns_capture_defaults(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.get(f"/public/widgets/{ch.public_key}/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contact_capture_enabled"] is False
    assert body["require_name"] is False
    assert body["require_email"] is False
    assert body["require_phone"] is False


def test_get_config_returns_capture_settings_when_enabled(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {
        "contact_capture_enabled": True,
        "require_name": True,
        "require_email": True,
        "require_phone": False,
    }
    db.commit()

    resp = public_client.get(f"/public/widgets/{ch.public_key}/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contact_capture_enabled"] is True
    assert body["require_name"] is True
    assert body["require_email"] is True
    assert body["require_phone"] is False


# ── POST /sessions contact_captured flag ──────────────────────────────────────

def test_session_contact_captured_true_when_capture_disabled(
    db: Session, workspace_a: Workspace, public_client
):
    """capture_enabled=False → contact_captured=True (no form needed)."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.post(f"/public/widgets/{ch.public_key}/sessions", json={})
    assert resp.status_code == 200
    assert resp.json()["contact_captured"] is True


def test_session_contact_captured_false_when_capture_enabled_new_session(
    db: Session, workspace_a: Workspace, public_client
):
    """capture_enabled=True, fresh session → contact_captured=False."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_name": True}
    db.commit()

    resp = public_client.post(f"/public/widgets/{ch.public_key}/sessions", json={})
    assert resp.status_code == 200
    assert resp.json()["contact_captured"] is False


def test_session_contact_captured_true_after_contact_filled(
    db: Session, workspace_a: Workspace, public_client
):
    """Resuming session where contact already has required fields → contact_captured=True."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_name": True}
    db.commit()

    ws = _make_session(db, ch, workspace_a.id)

    # Manually fill contact name.
    contact = db.get(Contact, ws.contact_id)
    contact.name = "Lucas Couto"
    db.commit()

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={"session_token": ws.session_token},
    )
    assert resp.status_code == 200
    assert resp.json()["contact_captured"] is True


# ── PATCH /session/contact ────────────────────────────────────────────────────

def _patch_contact(client, public_key: str, token: str, payload: dict):
    return client.patch(
        f"/public/widgets/{public_key}/session/contact",
        json=payload,
        headers={"X-Session-Token": token},
    )


def test_update_contact_name(db: Session, workspace_a: Workspace, public_client):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_name": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(public_client, ch.public_key, ws.session_token, {"name": "Lucas"})
    assert resp.status_code == 204

    db.expire_all()
    contact = db.get(Contact, ws.contact_id)
    assert contact.name == "Lucas"


def test_update_contact_email(db: Session, workspace_a: Workspace, public_client):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_email": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(
        public_client, ch.public_key, ws.session_token, {"email": "lucas@email.com"}
    )
    assert resp.status_code == 204

    db.expire_all()
    contact = db.get(Contact, ws.contact_id)
    assert contact.email == "lucas@email.com"


def test_update_contact_phone(db: Session, workspace_a: Workspace, public_client):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_phone": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(
        public_client, ch.public_key, ws.session_token, {"phone": "+5531999999999"}
    )
    assert resp.status_code == 204

    db.expire_all()
    contact = db.get(Contact, ws.contact_id)
    assert contact.phone == "+5531999999999"


def test_update_contact_all_fields(db: Session, workspace_a: Workspace, public_client):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {
        "contact_capture_enabled": True,
        "require_name": True,
        "require_email": True,
        "require_phone": True,
    }
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(
        public_client, ch.public_key, ws.session_token,
        {"name": "Lucas Couto", "email": "lucas@email.com", "phone": "+5531999999999"},
    )
    assert resp.status_code == 204


def test_update_contact_requires_session_token(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.patch(
        f"/public/widgets/{ch.public_key}/session/contact",
        json={"name": "Lucas"},
    )
    assert resp.status_code == 401


def test_update_contact_invalid_token(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = _patch_contact(public_client, ch.public_key, "wss_invalid", {"name": "Lucas"})
    assert resp.status_code == 401


def test_update_contact_wrong_channel_token(
    db: Session, workspace_a: Workspace, public_client
):
    """Token from channel A cannot be used on channel B."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch_a = _make_channel(db, workspace_a.id, agent.id)
    ch_b = _make_channel(db, workspace_a.id, agent.id)
    ws_a = _make_session(db, ch_a, workspace_a.id)

    resp = _patch_contact(public_client, ch_b.public_key, ws_a.session_token, {"name": "Lucas"})
    assert resp.status_code == 401


def test_update_contact_name_required_but_missing(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_name": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(public_client, ch.public_key, ws.session_token, {})
    assert resp.status_code == 422


def test_update_contact_email_required_but_invalid(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_email": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(
        public_client, ch.public_key, ws.session_token, {"email": "not-an-email"}
    )
    assert resp.status_code == 422


def test_update_contact_phone_required_but_missing(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_phone": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(public_client, ch.public_key, ws.session_token, {})
    assert resp.status_code == 422


def test_update_contact_non_required_field_still_saved(
    db: Session, workspace_a: Workspace, public_client
):
    """If a field is not required but supplied and valid, it should be saved."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_name": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = _patch_contact(
        public_client, ch.public_key, ws.session_token,
        {"name": "Lucas", "email": "lucas@email.com"},  # email not required but valid
    )
    assert resp.status_code == 204

    db.expire_all()
    contact = db.get(Contact, ws.contact_id)
    assert contact.email == "lucas@email.com"


def test_update_contact_origin_not_allowed(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(
        db, workspace_a.id, agent.id, allowed_origins=["https://allowed.example.com"]
    )
    ws = _make_session(db, ch, workspace_a.id)

    resp = public_client.patch(
        f"/public/widgets/{ch.public_key}/session/contact",
        json={"name": "Lucas"},
        headers={"X-Session-Token": ws.session_token, "Origin": "https://evil.example.com"},
    )
    assert resp.status_code == 403


# ── POST /messages blocked when capture required ──────────────────────────────

def test_message_blocked_when_capture_required_and_incomplete(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_name": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/messages",
        json={"content": "hello"},
        headers={"X-Session-Token": ws.session_token},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "contact_required"


def test_message_allowed_after_contact_captured(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ch.config_json = {"contact_capture_enabled": True, "require_name": True}
    db.commit()
    ws = _make_session(db, ch, workspace_a.id)

    # Capture contact first.
    patch = _patch_contact(public_client, ch.public_key, ws.session_token, {"name": "Lucas"})
    assert patch.status_code == 204

    # Now sending a message should work.
    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/messages",
        json={"content": "hello"},
        headers={"X-Session-Token": ws.session_token},
    )
    assert resp.status_code == 201


def test_message_allowed_when_capture_disabled(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)  # capture disabled (default)
    ws = _make_session(db, ch, workspace_a.id)

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/messages",
        json={"content": "hello"},
        headers={"X-Session-Token": ws.session_token},
    )
    assert resp.status_code == 201
