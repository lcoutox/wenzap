"""
Tests for Phase 5.7 — Widget Source Tracking / Attribution.

Covers:
- WidgetPageContext schema validation (trim, nullify, max length)
- New session saves attribution in Contact.metadata_json
- Existing session updates last_seen, does NOT overwrite first attribution
- UTMs preserved on first value
- page_context absent → behavior unchanged
- Invalid/foreign session token → creates new session with attribution
- ConversationOut includes attribution fields
- Tenant isolation: attribution from another workspace not leaked
"""

import pytest
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.workspace import Workspace
from app.schemas.public_widget import WidgetPageContext
from tests.test_widget_messages import _make_agent_simple, _make_channel, _make_session

# ── WidgetPageContext schema ───────────────────────────────────────────────────


def test_page_context_valid():
    ctx = WidgetPageContext(
        page_url="https://exemplo.com/precos",
        page_title="Preços",
        referrer="https://google.com",
        utm_source="google",
        utm_medium="cpc",
        utm_campaign="growth",
        utm_term="chatbot ia",
        utm_content="hero",
    )
    assert ctx.page_url == "https://exemplo.com/precos"
    assert ctx.utm_source == "google"


def test_page_context_trims_whitespace():
    ctx = WidgetPageContext(page_url="  https://exemplo.com  ", utm_source="  google  ")
    assert ctx.page_url == "https://exemplo.com"
    assert ctx.utm_source == "google"


def test_page_context_empty_string_becomes_none():
    ctx = WidgetPageContext(page_url="", utm_source="   ")
    assert ctx.page_url is None
    assert ctx.utm_source is None


def test_page_context_all_optional():
    ctx = WidgetPageContext()
    assert ctx.page_url is None
    assert ctx.utm_campaign is None


def test_page_context_page_url_too_long():
    with pytest.raises(Exception):
        WidgetPageContext(page_url="https://a.com/" + "x" * 2040)


def test_page_context_utm_source_too_long():
    with pytest.raises(Exception):
        WidgetPageContext(utm_source="x" * 201)


def test_page_context_page_title_too_long():
    with pytest.raises(Exception):
        WidgetPageContext(page_title="x" * 301)


# ── Session attribution — new session ────────────────────────────────────────

_FULL_CONTEXT = {
    "page_url": "https://cliente.com/precos?utm_source=google",
    "page_title": "Preços | Cliente",
    "referrer": "https://google.com",
    "utm_source": "google",
    "utm_medium": "cpc",
    "utm_campaign": "growth",
    "utm_term": "chatbot",
    "utm_content": "hero",
}


def test_new_session_saves_attribution(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={"page_context": _FULL_CONTEXT},
    )
    assert resp.status_code == 200
    token = resp.json()["session_token"]

    # Find the session and its contact.
    from sqlalchemy import select

    from app.models.widget_session import WidgetSession

    ws = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token))
    assert ws is not None
    contact = db.get(Contact, ws.contact_id)
    assert contact is not None
    meta = contact.metadata_json
    assert meta["attribution"]["first_page_url"] == "https://cliente.com/precos?utm_source=google"
    assert meta["attribution"]["utm_source"] == "google"
    assert meta["attribution"]["utm_campaign"] == "growth"
    assert meta["attribution"]["first_referrer"] == "https://google.com"


def test_new_session_saves_last_seen(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={"page_context": _FULL_CONTEXT},
    )
    token = resp.json()["session_token"]

    from sqlalchemy import select

    from app.models.widget_session import WidgetSession

    ws = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token))
    contact = db.get(Contact, ws.contact_id)
    meta = contact.metadata_json
    assert meta["last_seen"]["page_url"] == "https://cliente.com/precos?utm_source=google"


def test_new_session_preserves_existing_metadata_keys(
    db: Session, workspace_a: Workspace, public_client
):
    """Source/channel_id/public_key written on contact creation must not be removed."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={"page_context": _FULL_CONTEXT},
    )
    token = resp.json()["session_token"]

    from sqlalchemy import select

    from app.models.widget_session import WidgetSession

    ws = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token))
    contact = db.get(Contact, ws.contact_id)
    meta = contact.metadata_json
    assert meta["source"] == "web_widget"
    assert "channel_id" in meta
    assert meta["public_key"] == ch.public_key


def test_session_without_context_behavior_unchanged(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.post(f"/public/widgets/{ch.public_key}/sessions", json={})
    assert resp.status_code == 200
    token = resp.json()["session_token"]

    from sqlalchemy import select

    from app.models.widget_session import WidgetSession

    ws = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token))
    contact = db.get(Contact, ws.contact_id)
    meta = contact.metadata_json
    # No attribution key if no page_context was sent.
    assert "attribution" not in meta


# ── Session attribution — resume ──────────────────────────────────────────────

def test_resume_updates_last_seen(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ws = _make_session(db, ch, workspace_a.id)

    # Resume with a new page.
    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={
            "session_token": ws.session_token,
            "page_context": {"page_url": "https://cliente.com/contato", "page_title": "Contato"},
        },
    )
    assert resp.status_code == 200

    db.expire_all()
    contact = db.get(Contact, ws.contact_id)
    meta = contact.metadata_json
    assert meta["last_seen"]["page_url"] == "https://cliente.com/contato"


def test_resume_does_not_overwrite_first_attribution(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    # First session with utm_source=google.
    resp1 = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={"page_context": {"page_url": "https://a.com", "utm_source": "google"}},
    )
    token = resp1.json()["session_token"]

    # Resume with utm_source=facebook.
    public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={
            "session_token": token,
            "page_context": {"page_url": "https://b.com", "utm_source": "facebook"},
        },
    )

    from sqlalchemy import select

    from app.models.widget_session import WidgetSession

    db.expire_all()
    ws = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token))
    contact = db.get(Contact, ws.contact_id)
    meta = contact.metadata_json
    # First attribution must remain google.
    assert meta["attribution"]["utm_source"] == "google"
    assert meta["attribution"]["first_page_url"] == "https://a.com"
    # But last_seen should reflect latest page.
    assert meta["last_seen"]["page_url"] == "https://b.com"


def test_resume_fills_attribution_if_missing(
    db: Session, workspace_a: Workspace, public_client
):
    """If session was created without context, first resume with context sets attribution."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ws = _make_session(db, ch, workspace_a.id)

    # Verify no attribution yet.
    contact_before = db.get(Contact, ws.contact_id)
    assert "attribution" not in (contact_before.metadata_json or {})

    # Resume with context.
    public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={
            "session_token": ws.session_token,
            "page_context": {"page_url": "https://a.com", "utm_source": "email"},
        },
    )

    db.expire_all()
    contact = db.get(Contact, ws.contact_id)
    meta = contact.metadata_json
    assert meta["attribution"]["first_page_url"] == "https://a.com"
    assert meta["attribution"]["utm_source"] == "email"


def test_invalid_token_creates_new_session_with_attribution(
    db: Session, workspace_a: Workspace, public_client
):
    """An invalid session_token is ignored, new session created with page_context."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={
            "session_token": "wss_does_not_exist",
            "page_context": {"page_url": "https://a.com", "utm_source": "organic"},
        },
    )
    assert resp.status_code == 200
    token = resp.json()["session_token"]
    assert token != "wss_does_not_exist"

    from sqlalchemy import select

    from app.models.widget_session import WidgetSession

    ws = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token))
    contact = db.get(Contact, ws.contact_id)
    assert contact.metadata_json["attribution"]["utm_source"] == "organic"


# ── ConversationOut attribution fields ────────────────────────────────────────

def test_conversation_out_includes_attribution(
    db: Session, workspace_a: Workspace, public_client, client_a
):
    """GET /conversations includes source_page_url etc. when attribution is stored."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    # Create session with attribution.
    resp = public_client.post(
        f"/public/widgets/{ch.public_key}/sessions",
        json={"page_context": _FULL_CONTEXT},
    )
    token = resp.json()["session_token"]

    from sqlalchemy import select

    from app.models.widget_session import WidgetSession

    ws = db.scalar(select(WidgetSession).where(WidgetSession.session_token == token))

    # Now fetch conversation from the internal API.
    conv_resp = client_a.get(f"/conversations/{ws.conversation_id}")
    assert conv_resp.status_code == 200
    body = conv_resp.json()
    assert body["source_page_url"] == "https://cliente.com/precos?utm_source=google"
    assert body["source_page_title"] == "Preços | Cliente"
    assert body["utm_source"] == "google"
    assert body["utm_campaign"] == "growth"


def test_conversation_out_attribution_null_when_missing(
    db: Session, workspace_a: Workspace, public_client, client_a
):
    """Conversations without attribution return null fields."""
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)
    ws = _make_session(db, ch, workspace_a.id)  # no page_context

    conv_resp = client_a.get(f"/conversations/{ws.conversation_id}")
    assert conv_resp.status_code == 200
    body = conv_resp.json()
    assert body["source_page_url"] is None
    assert body["utm_source"] is None


# ── Public safety ─────────────────────────────────────────────────────────────

def test_config_does_not_expose_attribution(
    db: Session, workspace_a: Workspace, public_client
):
    agent = _make_agent_simple(db, workspace_a.id)
    ch = _make_channel(db, workspace_a.id, agent.id)

    resp = public_client.get(f"/public/widgets/{ch.public_key}/config")
    body = resp.json()
    assert "attribution" not in body
    assert "metadata_json" not in body
    assert "page_url" not in body
