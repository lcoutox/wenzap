"""
Tests for Pipeline.2 — automation (webhook, entry_condition, stay_limit,
stage entry actions, history/metrics).

Mirrors the fixture/mocking conventions of test_pipelines.py and
test_agent_test_rag.py (LLM patched at app.llm.client.complete).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.schemas import LLMResponse
from app.models.agent import Agent
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.pipeline import Pipeline
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_entry_stage_history import PipelineEntryStageHistory
from app.models.pipeline_stage import PipelineStage
from app.services.pipeline_auto_routing_service import maybe_route_conversation
from app.services.pipeline_stay_limit_scheduler import run_sweep_once
from app.services.pipeline_webhook_service import WebhookUrlError, validate_webhook_url
from tests.conftest import _make_client, _make_user, _make_workspace  # noqa: F401 — re-exported

_LLM_PATCH = "app.llm.client.complete"


def _mock_llm(content: str) -> LLMResponse:
    return LLMResponse(content=content, input_tokens=10, output_tokens=10, duration_ms=5)


# ── Helpers (same shape as test_pipelines.py) ────────────────────────────────


def _make_pipeline(db: Session, workspace_id: uuid.UUID, name: str = "Sales") -> Pipeline:
    p = Pipeline(workspace_id=workspace_id, name=name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_stage(db: Session, workspace_id: uuid.UUID, pipeline_id: uuid.UUID, **kwargs) -> PipelineStage:
    s = PipelineStage(workspace_id=workspace_id, pipeline_id=pipeline_id, **kwargs)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_contact(db: Session, workspace_id: uuid.UUID, name: str | None = "Test Contact") -> Contact:
    c = Contact(workspace_id=workspace_id, name=name, phone="+5511999999999" if name else None)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_conversation(db: Session, workspace_id: uuid.UUID, contact_id: uuid.UUID) -> Conversation:
    c = Conversation(
        workspace_id=workspace_id, contact_id=contact_id,
        channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_entry(
    db: Session, workspace_id: uuid.UUID, pipeline_id: uuid.UUID,
    conversation_id: uuid.UUID, stage_id: uuid.UUID | None, entered_stage_at=None,
) -> PipelineEntry:
    e = PipelineEntry(
        workspace_id=workspace_id, pipeline_id=pipeline_id, stage_id=stage_id,
        conversation_id=conversation_id, status="active",
        entered_stage_at=entered_stage_at or datetime.now(timezone.utc),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ── Fase 0: pipelines_limit ───────────────────────────────────────────────────


def test_pipelines_limit_enforced(db, client_a, subscription_a):
    """Starter test plan has pipelines_limit=1 (see `plan` fixture)."""
    resp1 = client_a.post("/pipelines", json={"name": "First"})
    assert resp1.status_code == 201

    resp2 = client_a.post("/pipelines", json={"name": "Second"})
    assert resp2.status_code == 402


def test_pipelines_limit_not_enforced_when_unlimited(db, client_a, growth_subscription_a):
    """Growth test plan has pipelines_limit=5 — well within range for this test."""
    for i in range(3):
        resp = client_a.post("/pipelines", json={"name": f"Pipeline {i}"})
        assert resp.status_code == 201


# ── Fase 1: webhook ────────────────────────────────────────────────────────────


def test_webhook_url_rejects_private_ip():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
        try:
            validate_webhook_url("http://internal.example.com/hook")
        except WebhookUrlError:
            pass
        else:
            raise AssertionError("expected WebhookUrlError for private IP")


def test_webhook_url_accepts_public_ip():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]):
        validate_webhook_url("https://example.com/hook")  # should not raise


def test_create_stage_rejects_private_webhook_url(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 0))]):
        resp = client_a.post(
            f"/pipelines/{p.id}/stages",
            json={"name": "S1", "position": 0, "webhook_url": "http://localhost:8000/hook"},
        )
    assert resp.status_code == 422


def test_webhook_dispatched_on_manual_move(db, client_a, scale_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(
        db, workspace_a.id, p.id, name="S2", position=1,
        webhook_url="https://example.com/hook",
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]), \
         patch("httpx.post") as mock_post, \
         patch("threading.Thread") as mock_thread_cls:
        # Run the dispatch synchronously instead of in a real daemon thread.
        def _run_target_now(target=None, args=(), **kwargs):
            target(*args)
            return MagicMock(start=lambda: None)
        mock_thread_cls.side_effect = _run_target_now
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)

        resp = client_a.post(
            f"/pipelines/{p.id}/entries/{entry.id}/move", json={"stage_id": str(s2.id)}
        )
        assert resp.status_code == 200
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["event"] == "STAGE_ENTERED"
        assert payload["stage_id"] == str(s2.id)
        assert payload["previous_stage_id"] == str(s1.id)


def test_webhook_not_dispatched_without_automations_feature(
    db, client_a, growth_subscription_a, workspace_a,
):
    """Growth plan does not have pipeline_automations — webhook must not fire."""
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(
        db, workspace_a.id, p.id, name="S2", position=1,
        webhook_url="https://example.com/hook",
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    with patch("threading.Thread") as mock_thread_cls:
        resp = client_a.post(
            f"/pipelines/{p.id}/entries/{entry.id}/move", json={"stage_id": str(s2.id)}
        )
        assert resp.status_code == 200
        mock_thread_cls.assert_not_called()


# ── Fase 4: stage entry actions ───────────────────────────────────────────────


def test_on_enter_actions_applied_on_move(db, client_a, scale_subscription_a, workspace_a, user_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(
        db, workspace_a.id, p.id, name="S2", position=1,
        on_enter_conversation_status="resolved",
        on_enter_assigned_user_id=user_a.id,
        on_enter_ai_enabled=False,
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    resp = client_a.post(
        f"/pipelines/{p.id}/entries/{entry.id}/move", json={"stage_id": str(s2.id)}
    )
    assert resp.status_code == 200

    db.refresh(conv)
    assert conv.status == "resolved"
    assert conv.assigned_user_id == user_a.id
    assert conv.ai_enabled is False


def test_on_enter_actions_not_applied_without_automations(
    db, client_a, growth_subscription_a, workspace_a, user_a,
):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(
        db, workspace_a.id, p.id, name="S2", position=1,
        on_enter_conversation_status="resolved",
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    resp = client_a.post(
        f"/pipelines/{p.id}/entries/{entry.id}/move", json={"stage_id": str(s2.id)}
    )
    assert resp.status_code == 200
    db.refresh(conv)
    assert conv.status == "open"  # unchanged — Growth plan has no automations


def test_is_removal_stage_marks_entry_inactive(db, client_a, growth_subscription_a, workspace_a):
    """is_removal_stage is a manual causal effect — not gated by pipeline_automations."""
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(db, workspace_a.id, p.id, name="Fechado", position=1, is_removal_stage=True)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    resp = client_a.post(
        f"/pipelines/{p.id}/entries/{entry.id}/move", json={"stage_id": str(s2.id)}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "inactive"


def test_request_contact_info_injects_missing_fields_prompt(db, workspace_a):
    from app.models.agent_prompt_settings import AgentPromptSettings
    from app.models.conversation_message import ConversationMessage
    from app.services.conversation_context_builder import build_conversation_context

    p = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(
        db, workspace_a.id, p.id, name="Coleta", position=0, request_contact_info=True
    )
    contact = _make_contact(db, workspace_a.id, name=None)  # no name/email/phone
    agent = Agent(workspace_id=workspace_a.id, name="Agent")
    db.add(agent)
    db.commit()
    db.refresh(agent)
    db.add(AgentPromptSettings(agent_id=agent.id, system_prompt="Você é um assistente."))
    db.commit()

    conv = Conversation(
        workspace_id=workspace_a.id, contact_id=contact.id, agent_id=agent.id,
        channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    _make_entry(db, workspace_a.id, p.id, conv.id, stage.id)

    msg = ConversationMessage(
        workspace_id=workspace_a.id, conversation_id=conv.id,
        direction="inbound", sender_type="customer", content="Oi", content_type="text",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    ctx = build_conversation_context(db, workspace_a.id, conv, agent, msg)
    assert "COLETA DE DADOS" in ctx.system_prompt
    assert "nome" in ctx.system_prompt


# ── Fase 5: history / metrics ─────────────────────────────────────────────────


def test_stage_history_recorded_on_moves(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(db, workspace_a.id, p.id, name="S2", position=1)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    client_a.post(f"/pipelines/{p.id}/entries/{entry.id}/move", json={"stage_id": str(s2.id)})

    rows = db.scalars(
        select(PipelineEntryStageHistory)
        .where(PipelineEntryStageHistory.entry_id == entry.id)
        .order_by(PipelineEntryStageHistory.entered_at.asc())
    ).all()
    assert len(rows) == 1  # only the move via API created a row — initial creation used the raw helper
    assert rows[0].stage_id == s2.id
    assert rows[0].moved_by == "manual"

    resp = client_a.get(f"/pipelines/{p.id}/entries/{entry.id}/history")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_pipeline_metrics_endpoint(db, client_a, growth_subscription_a, workspace_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(db, workspace_a.id, p.id, name="S2", position=1)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    client_a.post(f"/pipelines/{p.id}/entries/{entry.id}/move", json={"stage_id": str(s2.id)})

    resp = client_a.get(f"/pipelines/{p.id}/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_entries"] == 1
    assert len(body["stage_metrics"]) == 2


# ── Fase 2: entry_condition auto-routing ──────────────────────────────────────


def test_entry_condition_routes_conversation(db, workspace_a, scale_subscription_a):
    from app.models.conversation_message import ConversationMessage

    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    s2 = _make_stage(
        db, workspace_a.id, p.id, name="Qualificado", position=1,
        entry_condition="Cliente confirmou interesse em comprar",
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    msg = ConversationMessage(
        workspace_id=workspace_a.id, conversation_id=conv.id,
        direction="inbound", sender_type="customer", content="Quero comprar!",
        content_type="text",
    )
    db.add(msg)
    db.commit()

    fake_response = _mock_llm(f'{{"should_move": true, "target_stage_id": "{s2.id}"}}')
    with patch(_LLM_PATCH, return_value=fake_response):
        maybe_route_conversation(db, workspace_a.id, conv)

    db.refresh(entry)
    assert entry.stage_id == s2.id


def test_entry_condition_does_not_route_without_automations_feature(
    db, workspace_a, growth_subscription_a,
):
    from app.models.conversation_message import ConversationMessage

    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    _make_stage(
        db, workspace_a.id, p.id, name="Qualificado", position=1,
        entry_condition="Cliente confirmou interesse",
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    msg = ConversationMessage(
        workspace_id=workspace_a.id, conversation_id=conv.id,
        direction="inbound", sender_type="customer", content="Quero comprar!",
        content_type="text",
    )
    db.add(msg)
    db.commit()

    with patch(_LLM_PATCH) as mock_llm:
        maybe_route_conversation(db, workspace_a.id, conv)
        mock_llm.assert_not_called()  # gated out before ever calling the classifier

    db.refresh(entry)
    assert entry.stage_id == s1.id


def test_entry_condition_ignores_invalid_target_stage(db, workspace_a, scale_subscription_a):
    from app.models.conversation_message import ConversationMessage

    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(db, workspace_a.id, p.id, name="S1", position=0)
    _make_stage(
        db, workspace_a.id, p.id, name="Qualificado", position=1,
        entry_condition="Cliente confirmou interesse",
    )
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)

    msg = ConversationMessage(
        workspace_id=workspace_a.id, conversation_id=conv.id,
        direction="inbound", sender_type="customer", content="oi",
        content_type="text",
    )
    db.add(msg)
    db.commit()

    # Model hallucinates a stage id that isn't one of the real candidates.
    fake_response = _mock_llm(f'{{"should_move": true, "target_stage_id": "{uuid.uuid4()}"}}')
    with patch(_LLM_PATCH, return_value=fake_response):
        maybe_route_conversation(db, workspace_a.id, conv)

    db.refresh(entry)
    assert entry.stage_id == s1.id  # unchanged


# ── Fase 3: stay_limit sweep ───────────────────────────────────────────────────


def test_stay_limit_sweep_advances_expired_entry(db, workspace_a, scale_subscription_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(
        db, workspace_a.id, p.id, name="S1", position=0,
        stay_limit_enabled=True, stay_limit_minutes=10,
    )
    s2 = _make_stage(db, workspace_a.id, p.id, name="S2", position=1)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entered_long_ago = datetime.now(timezone.utc) - timedelta(minutes=20)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id, entered_stage_at=entered_long_ago)

    moved = run_sweep_once(db)
    assert moved == 1

    db.refresh(entry)
    assert entry.stage_id == s2.id


def test_stay_limit_sweep_skips_not_yet_expired(db, workspace_a, scale_subscription_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(
        db, workspace_a.id, p.id, name="S1", position=0,
        stay_limit_enabled=True, stay_limit_minutes=60,
    )
    _make_stage(db, workspace_a.id, p.id, name="S2", position=1)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id)  # just entered

    moved = run_sweep_once(db)
    assert moved == 0
    db.refresh(entry)
    assert entry.stage_id == s1.id


def test_stay_limit_sweep_skips_without_automations_feature(db, workspace_a, growth_subscription_a):
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(
        db, workspace_a.id, p.id, name="S1", position=0,
        stay_limit_enabled=True, stay_limit_minutes=10,
    )
    _make_stage(db, workspace_a.id, p.id, name="S2", position=1)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entered_long_ago = datetime.now(timezone.utc) - timedelta(minutes=20)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id, entered_stage_at=entered_long_ago)

    moved = run_sweep_once(db)
    assert moved == 0  # Growth has no pipeline_automations
    db.refresh(entry)
    assert entry.stage_id == s1.id


def test_stay_limit_sweep_compare_and_swap_prevents_double_move(db, workspace_a, scale_subscription_a):
    """Simulates a lost race: the entry moved between SELECT and UPDATE."""
    p = _make_pipeline(db, workspace_a.id)
    s1 = _make_stage(
        db, workspace_a.id, p.id, name="S1", position=0,
        stay_limit_enabled=True, stay_limit_minutes=10,
    )
    s2 = _make_stage(db, workspace_a.id, p.id, name="S2", position=1)
    s3 = _make_stage(db, workspace_a.id, p.id, name="S3", position=2)
    contact = _make_contact(db, workspace_a.id)
    conv = _make_conversation(db, workspace_a.id, contact.id)
    entered_long_ago = datetime.now(timezone.utc) - timedelta(minutes=20)
    entry = _make_entry(db, workspace_a.id, p.id, conv.id, s1.id, entered_stage_at=entered_long_ago)

    # Simulate a concurrent move that already happened.
    entry.stage_id = s3.id
    db.commit()

    from sqlalchemy import update as _update

    result = db.execute(
        _update(PipelineEntry)
        .where(PipelineEntry.id == entry.id, PipelineEntry.stage_id == s1.id)  # stale stage_id
        .values(stage_id=s2.id)
    )
    db.commit()
    assert result.rowcount == 0  # CAS correctly refuses — entry is no longer in s1
    db.refresh(entry)
    assert entry.stage_id == s3.id  # untouched by the failed CAS
