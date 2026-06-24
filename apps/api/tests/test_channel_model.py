"""
Tests for Phase 5.4.1 — Channel model.

Covers:
  - create channel with minimal valid data
  - defaults: status=active, config_json={}, allowed_origins=[]
  - public_key unique constraint
  - check constraint: channel_type
  - check constraint: status
  - FK workspace cascade
  - FK agent cascade
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.channel import Channel
from app.models.workspace import Workspace

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_agent(db: Session, workspace_id: uuid.UUID) -> Agent:
    agent = Agent(workspace_id=workspace_id, name="Test Agent", status="active")
    db.add(agent)
    db.flush()
    return agent


def _make_channel(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    *,
    channel_type: str = "web_widget",
    name: str = "My Widget",
    public_key: str | None = None,
    status: str = "active",
    config_json: dict | None = None,
    allowed_origins: list[str] | None = None,
) -> Channel:
    c = Channel(
        workspace_id=workspace_id,
        agent_id=agent_id,
        channel_type=channel_type,
        name=name,
        public_key=public_key or f"wgt_{uuid.uuid4().hex[:24]}",
        status=status,
        config_json=config_json if config_json is not None else {},
        allowed_origins=allowed_origins if allowed_origins is not None else [],
    )
    db.add(c)
    db.flush()
    return c


# ── Model tests ────────────────────────────────────────────────────────────────

def test_create_channel_minimal(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)
    db.commit()
    db.refresh(channel)

    assert channel.id is not None
    assert channel.workspace_id == workspace_a.id
    assert channel.agent_id == agent.id
    assert channel.channel_type == "web_widget"
    assert channel.name == "My Widget"
    assert channel.public_key.startswith("wgt_")
    assert channel.status == "active"
    assert channel.config_json == {}
    assert channel.allowed_origins == []
    assert channel.created_at is not None
    assert channel.updated_at is not None


def test_channel_defaults(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)
    db.commit()

    assert channel.status == "active"
    assert channel.config_json == {}
    assert channel.allowed_origins == []


def test_channel_with_config_and_origins(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    config = {"theme": "light", "primary_color": "#ff0000", "auto_open": True}
    origins = ["https://example.com", "https://www.example.com"]
    channel = _make_channel(
        db, workspace_a.id, agent.id, config_json=config, allowed_origins=origins
    )
    db.commit()
    db.refresh(channel)

    assert channel.config_json == config
    assert channel.allowed_origins == origins


def test_public_key_unique_constraint(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    key = "wgt_uniquekey123456789012"
    _make_channel(db, workspace_a.id, agent.id, public_key=key)
    db.commit()

    with pytest.raises(IntegrityError):
        _make_channel(db, workspace_a.id, agent.id, public_key=key)
    db.rollback()


def test_channel_type_check_constraint(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = Channel(
        workspace_id=workspace_a.id,
        agent_id=agent.id,
        channel_type="invalid_type",
        name="Bad",
        public_key=f"wgt_{uuid.uuid4().hex[:24]}",
        status="active",
        config_json={},
        allowed_origins=[],
    )
    db.add(channel)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_status_check_constraint(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = Channel(
        workspace_id=workspace_a.id,
        agent_id=agent.id,
        channel_type="web_widget",
        name="Bad Status",
        public_key=f"wgt_{uuid.uuid4().hex[:24]}",
        status="deleted",
        config_json={},
        allowed_origins=[],
    )
    db.add(channel)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_workspace_fk_cascade(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)
    db.commit()
    channel_id = channel.id

    db.execute(text("DELETE FROM workspaces WHERE id = :id"), {"id": workspace_a.id})
    db.commit()

    result = db.scalar(select(Channel).where(Channel.id == channel_id))
    assert result is None


def test_agent_fk_cascade(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    channel = _make_channel(db, workspace_a.id, agent.id)
    db.commit()
    channel_id = channel.id

    db.execute(text("DELETE FROM agents WHERE id = :id"), {"id": agent.id})
    db.commit()

    result = db.scalar(select(Channel).where(Channel.id == channel_id))
    assert result is None


def test_valid_channel_statuses(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    for s in ("active", "inactive", "archived"):
        ch = _make_channel(
            db, workspace_a.id, agent.id,
            status=s,
            public_key=f"wgt_{uuid.uuid4().hex[:24]}",
        )
        db.commit()
        assert ch.status == s


def test_valid_channel_types(db: Session, workspace_a: Workspace):
    agent = _make_agent(db, workspace_a.id)
    for ct in ("web_widget", "whatsapp", "instagram", "email", "api"):
        ch = _make_channel(
            db, workspace_a.id, agent.id,
            channel_type=ct,
            public_key=f"wgt_{uuid.uuid4().hex[:24]}",
        )
        db.commit()
        assert ch.channel_type == ct
