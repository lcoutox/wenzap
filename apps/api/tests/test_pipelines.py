"""
Tests for Pipeline.1 — Conversation Pipeline Foundation.

Covers: Pipeline CRUD, Stage CRUD, Entry CRUD, Agent pipeline settings,
auto-entry on conversation creation, extra_prompt injection, tenant isolation.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.pipeline import Pipeline
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_stage import PipelineStage
from tests.conftest import _make_client, _make_user, _make_workspace


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_pipeline(db: Session, workspace_id: uuid.UUID, name: str = "Sales") -> Pipeline:
    p = Pipeline(workspace_id=workspace_id, name=name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_stage(
    db: Session,
    workspace_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    name: str = "Stage 1",
    position: int = 0,
    extra_prompt: str | None = None,
) -> PipelineStage:
    s = PipelineStage(
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        name=name,
        position=position,
        extra_prompt=extra_prompt,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_contact(db: Session, workspace_id: uuid.UUID, name: str = "Test Contact") -> Contact:
    c = Contact(workspace_id=workspace_id, name=name, phone="+5511999999999")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_agent(db: Session, workspace_id: uuid.UUID, name: str = "Agent") -> Agent:
    a = Agent(workspace_id=workspace_id, name=name)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_conversation(
    db: Session,
    workspace_id: uuid.UUID,
    contact_id: uuid.UUID,
    agent_id: uuid.UUID | None = None,
) -> Conversation:
    c = Conversation(
        workspace_id=workspace_id,
        contact_id=contact_id,
        agent_id=agent_id,
        channel_type="internal",
        status="open",
        ai_enabled=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ── Pipeline CRUD ─────────────────────────────────────────────────────────────


def test_create_pipeline(db, client_a, growth_subscription_a):
    resp = client_a.post("/pipelines", json={"name": "Sales Pipeline"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Sales Pipeline"
    assert body["is_active"] is True


def test_list_pipelines_own_workspace_only(
    db, user_a, user_b, growth_subscription_a, subscription_b,
    workspace_a, workspace_b,
):
    _make_pipeline(db, workspace_a.id, "Pipeline A")
    _make_pipeline(db, workspace_b.id, "Pipeline B")

    with _make_client(db, user_a, workspace_a) as client:
        resp = client.get("/pipelines")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Pipeline A" in names
    assert "Pipeline B" not in names


def test_get_pipeline(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id, "My Pipeline")
    resp = client_a.get(f"/pipelines/{p.id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "My Pipeline"


def test_update_pipeline(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id, "Old Name")
    resp = client_a.patch(f"/pipelines/{p.id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_soft_delete_pipeline(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id, "To Delete")
    resp = client_a.delete(f"/pipelines/{p.id}")
    assert resp.status_code == 204
    db.refresh(p)
    assert p.is_active is False


def test_pipeline_cross_tenant_404(db, client_a, growth_subscription_a, workspace_b, user_b):
    p = _make_pipeline(db, workspace_b.id, "B's Pipeline")
    resp = client_a.get(f"/pipelines/{p.id}")
    assert resp.status_code == 404


# ── Stage CRUD ────────────────────────────────────────────────────────────────


def test_create_stage(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    resp = client_a.post(
        f"/pipelines/{p.id}/stages",
        json={"name": "Prospecting", "position": 0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Prospecting"
    assert body["pipeline_id"] == str(p.id)


def test_list_stages_ordered_by_position(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    _make_stage(db, workspace_a.id, p.id, "Third", position=2)
    _make_stage(db, workspace_a.id, p.id, "First", position=0)
    _make_stage(db, workspace_a.id, p.id, "Second", position=1)

    resp = client_a.get(f"/pipelines/{p.id}/stages")
    assert resp.status_code == 200
    stages = resp.json()
    assert [s["name"] for s in stages] == ["First", "Second", "Third"]


def test_update_stage(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s = _make_stage(db, workspace_a.id, p.id, "Original")
    resp = client_a.patch(
        f"/pipelines/{p.id}/stages/{s.id}",
        json={"name": "Updated", "extra_prompt": "Be concise"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Updated"
    assert body["extra_prompt"] == "Be concise"


def test_reorder_stages(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, "A", position=0)
    s2 = _make_stage(db, workspace_a.id, p.id, "B", position=1)

    resp = client_a.post(
        f"/pipelines/{p.id}/stages/reorder",
        json={
            "stages": [
                {"id": str(s1.id), "position": 1},
                {"id": str(s2.id), "position": 0},
            ]
        },
    )
    assert resp.status_code == 200
    stages = resp.json()
    assert stages[0]["name"] == "B"
    assert stages[1]["name"] == "A"


def test_delete_stage_with_entries_blocked(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s = _make_stage(db, workspace_a.id, p.id)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = PipelineEntry(
        workspace_id=workspace_a.id,
        pipeline_id=p.id,
        stage_id=s.id,
        conversation_id=conv.id,
        status="active",
    )
    db.add(entry)
    db.commit()

    resp = client_a.delete(f"/pipelines/{p.id}/stages/{s.id}")
    assert resp.status_code == 409


def test_delete_stage_without_entries_ok(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s = _make_stage(db, workspace_a.id, p.id)
    resp = client_a.delete(f"/pipelines/{p.id}/stages/{s.id}")
    assert resp.status_code == 204


def test_stage_cross_tenant_404(db, client_a, growth_subscription_a, workspace_b):
    p = _make_pipeline(db, workspace_b.id)
    resp = client_a.get(f"/pipelines/{p.id}/stages")
    assert resp.status_code == 404


# ── Entry CRUD ────────────────────────────────────────────────────────────────


def test_create_entry(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s = _make_stage(db, workspace_a.id, p.id)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)

    resp = client_a.post(
        f"/pipelines/{p.id}/entries",
        json={"conversation_id": str(conv.id), "stage_id": str(s.id)},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["conversation_id"] == str(conv.id)
    assert body["stage_id"] == str(s.id)
    assert body["status"] == "active"


def test_create_entry_conversation_wrong_workspace_rejected(
    db, client_a, growth_subscription_a, workspace_a, workspace_b,
):
    p = _make_pipeline(db, workspace_a.id)
    contact_b = _make_contact(db, workspace_b.id)
    conv_b = _make_conversation(db, workspace_b.id, contact_b.id)

    resp = client_a.post(
        f"/pipelines/{p.id}/entries",
        json={"conversation_id": str(conv_b.id)},
    )
    assert resp.status_code == 404


def test_create_entry_duplicate_pipeline_conversation_rejected(
    db, client_a, growth_subscription_a, workspace_a,
):
    p = _make_pipeline(db, workspace_a.id)
    s = _make_stage(db, workspace_a.id, p.id)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)

    client_a.post(
        f"/pipelines/{p.id}/entries",
        json={"conversation_id": str(conv.id), "stage_id": str(s.id)},
    )
    resp = client_a.post(
        f"/pipelines/{p.id}/entries",
        json={"conversation_id": str(conv.id), "stage_id": str(s.id)},
    )
    assert resp.status_code == 409


def test_move_entry_updates_stage_and_entered_stage_at(
    db, client_a, growth_subscription_a, workspace_a,
):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, "S1", position=0)
    s2 = _make_stage(db, workspace_a.id, p.id, "S2", position=1)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)

    create_resp = client_a.post(
        f"/pipelines/{p.id}/entries",
        json={"conversation_id": str(conv.id), "stage_id": str(s1.id)},
    )
    entry_id = create_resp.json()["id"]

    resp = client_a.post(
        f"/pipelines/{p.id}/entries/{entry_id}/move",
        json={"stage_id": str(s2.id)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["stage_id"] == str(s2.id)
    assert body["entered_stage_at"] is not None


def test_list_entries_includes_contact_data(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    contact = _make_contact(db, workspace_a.id, "John Doe")
    conv = _make_conversation(db, workspace_a.id, contact.id)

    client_a.post(
        f"/pipelines/{p.id}/entries",
        json={"conversation_id": str(conv.id)},
    )

    resp = client_a.get(f"/pipelines/{p.id}/entries")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["contact_name"] == "John Doe"
    assert entries[0]["conversation_status"] == "open"


def test_remove_entry_sets_status_removed(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)

    create_resp = client_a.post(
        f"/pipelines/{p.id}/entries",
        json={"conversation_id": str(conv.id)},
    )
    entry_id = create_resp.json()["id"]

    resp = client_a.delete(f"/pipelines/{p.id}/entries/{entry_id}")
    assert resp.status_code == 204

    entry = db.get(PipelineEntry, uuid.UUID(entry_id))
    assert entry is not None
    assert entry.status == "removed"


# ── Agent pipeline settings ───────────────────────────────────────────────────


def test_update_agent_pipeline_settings(db, client_a, growth_subscription_a, workspace_a):
    agent = _make_agent(db, workspace_a.id)
    p = _make_pipeline(db, workspace_a.id)
    s = _make_stage(db, workspace_a.id, p.id)

    resp = client_a.patch(
        f"/agents/{agent.id}/pipeline-settings",
        json={
            "default_pipeline_id": str(p.id),
            "default_pipeline_stage_id": str(s.id),
        },
    )
    assert resp.status_code == 200
    db.refresh(agent)
    assert agent.default_pipeline_id == p.id
    assert agent.default_pipeline_stage_id == s.id


def test_update_agent_pipeline_settings_stage_wrong_pipeline_rejected(
    db, client_a, growth_subscription_a, workspace_a,
):
    agent = _make_agent(db, workspace_a.id)
    p1 = _make_pipeline(db, workspace_a.id, "P1")
    p2 = _make_pipeline(db, workspace_a.id, "P2")
    s2 = _make_stage(db, workspace_a.id, p2.id, "Stage of P2")

    resp = client_a.patch(
        f"/agents/{agent.id}/pipeline-settings",
        json={
            "default_pipeline_id": str(p1.id),
            "default_pipeline_stage_id": str(s2.id),
        },
    )
    assert resp.status_code == 422


def test_new_conversation_creates_pipeline_entry_automatically(
    db, client_a, growth_subscription_a, workspace_a,
):
    agent = _make_agent(db, workspace_a.id)
    p = _make_pipeline(db, workspace_a.id)
    s = _make_stage(db, workspace_a.id, p.id)
    agent.default_pipeline_id = p.id
    agent.default_pipeline_stage_id = s.id
    db.commit()

    resp = client_a.post(
        "/conversations",
        json={
            "contact_name": "Auto Entry Contact",
            "agent_id": str(agent.id),
            "channel_type": "internal",
            "ai_enabled": False,
        },
    )
    assert resp.status_code == 201
    conv_id = uuid.UUID(resp.json()["id"])

    entry = db.scalar(
        select(PipelineEntry).where(PipelineEntry.conversation_id == conv_id)
    )
    assert entry is not None
    assert entry.pipeline_id == p.id
    assert entry.stage_id == s.id
    assert entry.status == "active"


def test_agent_without_pipeline_no_entry_created(
    db, client_a, growth_subscription_a, workspace_a,
):
    agent = _make_agent(db, workspace_a.id)

    resp = client_a.post(
        "/conversations",
        json={
            "contact_name": "No Pipeline Contact",
            "agent_id": str(agent.id),
            "channel_type": "internal",
            "ai_enabled": False,
        },
    )
    assert resp.status_code == 201
    conv_id = uuid.UUID(resp.json()["id"])

    entry = db.scalar(
        select(PipelineEntry).where(PipelineEntry.conversation_id == conv_id)
    )
    assert entry is None


# ── Extra prompt injection ────────────────────────────────────────────────────


def test_extra_prompt_injected_when_conversation_in_stage_with_prompt(db, workspace_a):
    from unittest.mock import MagicMock

    from app.models.agent_prompt_settings import AgentPromptSettings
    from app.models.conversation_message import ConversationMessage
    from app.services.conversation_context_builder import build_conversation_context

    agent = _make_agent(db, workspace_a.id)
    prompt_settings = AgentPromptSettings(agent_id=agent.id, system_prompt="You are helpful.")
    db.add(prompt_settings)

    p = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(
        db, workspace_a.id, p.id, extra_prompt="Always be brief and direct."
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id, agent_id=agent.id)

    entry = PipelineEntry(
        workspace_id=workspace_a.id,
        pipeline_id=p.id,
        stage_id=stage.id,
        conversation_id=conv.id,
        contact_id=contact.id,
        status="active",
    )
    db.add(entry)

    msg = ConversationMessage(
        workspace_id=workspace_a.id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content_type="text",
        content="Hello",
    )
    db.add(msg)
    db.commit()

    import app.services.conversation_context_builder as ccb

    mock_rag = MagicMock(return_value=MagicMock(chunks=[], retrieval_duration_ms=0, error_message=None))
    mock_catalog = MagicMock(
        return_value=MagicMock(retrieval_attempted=False, items=[], context_block=None, error_message=None)
    )
    orig_rag = ccb.retrieve_context_for_agent
    orig_catalog = ccb.retrieve_catalog_context
    ccb.retrieve_context_for_agent = mock_rag
    ccb.retrieve_catalog_context = mock_catalog

    try:
        ctx = build_conversation_context(
            db=db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            trigger_message=msg,
        )
        assert ctx.pipeline_extra_prompt_injected is True
        assert "INSTRUÇÕES DESTA ETAPA" in ctx.system_prompt
        assert "Always be brief and direct." in ctx.system_prompt
    finally:
        ccb.retrieve_context_for_agent = orig_rag
        ccb.retrieve_catalog_context = orig_catalog


def test_extra_prompt_not_injected_when_no_active_entry(db, workspace_a):
    from unittest.mock import MagicMock

    from app.models.agent_prompt_settings import AgentPromptSettings
    from app.models.conversation_message import ConversationMessage
    from app.services.conversation_context_builder import build_conversation_context

    agent = _make_agent(db, workspace_a.id)
    prompt_settings = AgentPromptSettings(agent_id=agent.id, system_prompt="You are helpful.")
    db.add(prompt_settings)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id, agent_id=agent.id)

    msg = ConversationMessage(
        workspace_id=workspace_a.id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content_type="text",
        content="Hello",
    )
    db.add(msg)
    db.commit()

    import app.services.conversation_context_builder as ccb

    mock_rag = MagicMock(return_value=MagicMock(chunks=[], retrieval_duration_ms=0, error_message=None))
    mock_catalog = MagicMock(
        return_value=MagicMock(retrieval_attempted=False, items=[], context_block=None, error_message=None)
    )
    orig_rag = ccb.retrieve_context_for_agent
    orig_catalog = ccb.retrieve_catalog_context
    ccb.retrieve_context_for_agent = mock_rag
    ccb.retrieve_catalog_context = mock_catalog

    try:
        ctx = build_conversation_context(
            db=db,
            workspace_id=workspace_a.id,
            conversation=conv,
            agent=agent,
            trigger_message=msg,
        )
        assert ctx.pipeline_extra_prompt_injected is False
        assert "INSTRUÇÕES DESTA ETAPA" not in ctx.system_prompt
    finally:
        ccb.retrieve_context_for_agent = orig_rag
        ccb.retrieve_catalog_context = orig_catalog


# ── Security ──────────────────────────────────────────────────────────────────


def test_unverified_user_cannot_access_pipelines(unauthenticated_client):
    resp = unauthenticated_client.get("/pipelines")
    assert resp.status_code in (401, 403)


def test_cross_workspace_blocked(
    db, user_b, growth_subscription_a, subscription_b,
    workspace_a, workspace_b,
):
    p = _make_pipeline(db, workspace_a.id, "A's Pipeline")
    # client_b should not see workspace_a's pipeline
    with _make_client(db, user_b, workspace_b) as client:
        resp = client.get(f"/pipelines/{p.id}")
    assert resp.status_code == 404
