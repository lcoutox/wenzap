"""
Tests for Phase 5.3.5 — Human Take-over / Return to AI.

Covers:
  take-over
  - member/admin/owner can take over open conversation
  - sets assigned_user_id=current_user, ai_enabled=False
  - viewer gets 403
  - cross-workspace conversation returns 404
  - archived conversation returns 409
  - idempotent: take-over twice by same user succeeds

  return-to-ai
  - member/admin/owner can return to AI
  - sets assigned_user_id=None, ai_enabled=True
  - viewer gets 403
  - cross-workspace conversation returns 404
  - archived conversation returns 409
  - idempotent: return-to-ai twice succeeds

  interaction with auto-reply
  - after take-over, inbound/customer does NOT trigger auto-reply
  - after return-to-ai, inbound/customer triggers auto-reply again

  pending conversation
  - take-over and return-to-ai work on pending conversations
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import MemberRole, MemberStatus
from app.llm.schemas import LLMResponse
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.conversation_message import ConversationMessageCreate
from app.services.conversation_message_service import create_message
from app.services.conversation_service import return_to_ai, take_over_conversation
from tests.conftest import _make_client, _make_subscription, _make_user

# ── Constants ──────────────────────────────────────────────────────────────────

_LLM_PATCH = "app.llm.client.complete"
_MODEL_NAME = "claude-sonnet-4-6"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_member(db: Session, workspace: Workspace, role: MemberRole) -> object:
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


def _make_contact(db: Session, ws_id: uuid.UUID) -> Contact:
    c = Contact(workspace_id=ws_id, name="Cliente Teste")
    db.add(c)
    db.flush()
    return c


def _make_conv(
    db: Session,
    ws_id: uuid.UUID,
    agent: Agent | None = None,
    *,
    status: str = "open",
    ai_enabled: bool = True,
    assigned_user_id: uuid.UUID | None = None,
) -> Conversation:
    contact = _make_contact(db, ws_id)
    conv = Conversation(
        workspace_id=ws_id,
        contact_id=contact.id,
        agent_id=agent.id if agent else None,
        status=status,
        channel_type="internal",
        ai_enabled=ai_enabled,
        assigned_user_id=assigned_user_id,
    )
    db.add(conv)
    db.flush()
    db.refresh(conv)
    return conv


def _make_plan(db: Session) -> Plan:
    p = Plan(
        code=f"plan-{uuid.uuid4().hex[:8]}",
        name="Test",
        monthly_price_cents=0,
        currency="BRL",
        agents_limit=10,
        knowledge_bases_limit=10,
        sources_per_kb_limit=20,
        max_source_chars=50_000,
        users_limit=10,
        pipelines_limit=5,
        integrations_limit=5,
        monthly_ai_credits=5_000,
        monthly_conversations=5000,
        is_active=True,
    )
    db.add(p)
    db.flush()
    return p


def _make_counter(db: Session, ws_id: uuid.UUID) -> UsageCounter:
    now = datetime.now(timezone.utc)
    c = UsageCounter(
        workspace_id=ws_id,
        period_start=now - timedelta(hours=1),
        period_end=now + timedelta(days=30),
        ai_credits_used=0,
        conversations_count=0,
        messages_count=0,
    )
    db.add(c)
    db.flush()
    return c


def _make_ai_agent(db: Session, ws_id: uuid.UUID) -> Agent:
    provider = db.scalar(select(AiModelProvider).where(AiModelProvider.code == "anthropic"))
    if not provider:
        provider = AiModelProvider(code="anthropic", name="Anthropic", is_active=True)
        db.add(provider)
        db.flush()

    model = AiModel(
        provider_id=provider.id,
        code=f"model-{uuid.uuid4().hex[:8]}",
        display_name="Claude Sonnet",
        model_name=_MODEL_NAME,
        credits_per_message=2,
        min_plan_code="starter",
        is_active=True,
        sort_order=1,
    )
    db.add(model)
    db.flush()

    agent = Agent(workspace_id=ws_id, name="AI Agent", status="active")
    db.add(agent)
    db.flush()
    db.add(AgentPromptSettings(agent_id=agent.id, system_prompt="Help the user."))
    db.add(AgentModelSettings(
        agent_id=agent.id, ai_model_id=model.id, model_name=_MODEL_NAME, temperature=0.5
    ))
    db.flush()
    return agent


def _mock_llm() -> LLMResponse:
    return LLMResponse(
        content="Como posso ajudar?", input_tokens=50, output_tokens=20, duration_ms=300
    )


def _count_agent_replies(db: Session, conv_id: uuid.UUID) -> int:
    return len(db.scalars(
        select(ConversationMessage).where(
            ConversationMessage.conversation_id == conv_id,
            ConversationMessage.direction == "outbound",
            ConversationMessage.sender_type == "agent",
        )
    ).all())


# ── Take-over: service tests ───────────────────────────────────────────────────

def test_take_over_sets_fields(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conv(db, workspace_a.id)
    db.commit()

    result = take_over_conversation(db, workspace_a.id, conv.id, user_a.id)

    assert result["assigned_user_id"] == user_a.id
    assert result["ai_enabled"] is False


def test_take_over_pending_conversation(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conv(db, workspace_a.id, status="pending")
    db.commit()

    result = take_over_conversation(db, workspace_a.id, conv.id, user_a.id)

    assert result["assigned_user_id"] == user_a.id
    assert result["ai_enabled"] is False


def test_take_over_resolved_conversation(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conv(db, workspace_a.id, status="resolved")
    db.commit()

    result = take_over_conversation(db, workspace_a.id, conv.id, user_a.id)

    assert result["assigned_user_id"] == user_a.id


def test_take_over_archived_returns_409(db: Session, workspace_a: Workspace, user_a):
    from fastapi import HTTPException
    conv = _make_conv(db, workspace_a.id, status="archived")
    db.commit()

    try:
        take_over_conversation(db, workspace_a.id, conv.id, user_a.id)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 409


def test_take_over_cross_workspace_returns_404(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, user_a
):
    from fastapi import HTTPException
    conv = _make_conv(db, workspace_b.id)
    db.commit()

    try:
        take_over_conversation(db, workspace_a.id, conv.id, user_a.id)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404


def test_take_over_idempotent(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conv(db, workspace_a.id)
    db.commit()

    take_over_conversation(db, workspace_a.id, conv.id, user_a.id)
    result = take_over_conversation(db, workspace_a.id, conv.id, user_a.id)

    assert result["assigned_user_id"] == user_a.id
    assert result["ai_enabled"] is False


# ── Return-to-AI: service tests ────────────────────────────────────────────────

def test_return_to_ai_sets_fields(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conv(db, workspace_a.id, assigned_user_id=user_a.id, ai_enabled=False)
    db.commit()

    result = return_to_ai(db, workspace_a.id, conv.id)

    assert result["assigned_user_id"] is None
    assert result["ai_enabled"] is True


def test_return_to_ai_pending(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conv(
        db, workspace_a.id, status="pending", assigned_user_id=user_a.id, ai_enabled=False
    )
    db.commit()

    result = return_to_ai(db, workspace_a.id, conv.id)

    assert result["ai_enabled"] is True


def test_return_to_ai_archived_returns_409(db: Session, workspace_a: Workspace, user_a):
    from fastapi import HTTPException
    conv = _make_conv(
        db, workspace_a.id, status="archived", assigned_user_id=user_a.id, ai_enabled=False
    )
    db.commit()

    try:
        return_to_ai(db, workspace_a.id, conv.id)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 409


def test_return_to_ai_cross_workspace_returns_404(
    db: Session, workspace_a: Workspace, workspace_b: Workspace, user_a
):
    from fastapi import HTTPException
    conv = _make_conv(db, workspace_b.id, assigned_user_id=user_a.id, ai_enabled=False)
    db.commit()

    try:
        return_to_ai(db, workspace_a.id, conv.id)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404


def test_return_to_ai_idempotent(db: Session, workspace_a: Workspace, user_a):
    conv = _make_conv(db, workspace_a.id, ai_enabled=True)
    db.commit()

    return_to_ai(db, workspace_a.id, conv.id)
    result = return_to_ai(db, workspace_a.id, conv.id)

    assert result["ai_enabled"] is True
    assert result["assigned_user_id"] is None


# ── RBAC: HTTP endpoint tests ──────────────────────────────────────────────────

def test_take_over_member_allowed(db: Session, workspace_a: Workspace, client_a):
    member = _make_member(db, workspace_a, MemberRole.member)
    conv = _make_conv(db, workspace_a.id)
    db.commit()

    with _make_client(db, member, workspace_a) as client:
        resp = client.post(f"/conversations/{conv.id}/take-over")
    assert resp.status_code == 200
    assert resp.json()["ai_enabled"] is False


def test_take_over_admin_allowed(db: Session, workspace_a: Workspace, client_a):
    admin = _make_member(db, workspace_a, MemberRole.admin)
    conv = _make_conv(db, workspace_a.id)
    db.commit()

    with _make_client(db, admin, workspace_a) as client:
        resp = client.post(f"/conversations/{conv.id}/take-over")
    assert resp.status_code == 200


def test_take_over_owner_allowed(db: Session, workspace_a: Workspace, client_a):
    conv = _make_conv(db, workspace_a.id)
    db.commit()

    resp = client_a.post(f"/conversations/{conv.id}/take-over")
    assert resp.status_code == 200


def test_take_over_viewer_forbidden(db: Session, workspace_a: Workspace):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    conv = _make_conv(db, workspace_a.id)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        resp = client.post(f"/conversations/{conv.id}/take-over")
    assert resp.status_code == 403


def test_return_to_ai_member_allowed(db: Session, workspace_a: Workspace, user_a):
    member = _make_member(db, workspace_a, MemberRole.member)
    conv = _make_conv(db, workspace_a.id, assigned_user_id=user_a.id, ai_enabled=False)
    db.commit()

    with _make_client(db, member, workspace_a) as client:
        resp = client.post(f"/conversations/{conv.id}/return-to-ai")
    assert resp.status_code == 200
    assert resp.json()["ai_enabled"] is True


def test_return_to_ai_viewer_forbidden(db: Session, workspace_a: Workspace, user_a):
    viewer = _make_member(db, workspace_a, MemberRole.viewer)
    conv = _make_conv(db, workspace_a.id, assigned_user_id=user_a.id, ai_enabled=False)
    db.commit()

    with _make_client(db, viewer, workspace_a) as client:
        resp = client.post(f"/conversations/{conv.id}/return-to-ai")
    assert resp.status_code == 403


def test_take_over_http_archived_returns_409(db: Session, workspace_a: Workspace, client_a):
    conv = _make_conv(db, workspace_a.id, status="archived")
    db.commit()

    resp = client_a.post(f"/conversations/{conv.id}/take-over")
    assert resp.status_code == 409


def test_return_to_ai_http_archived_returns_409(
    db: Session, workspace_a: Workspace, user_a, client_a
):
    conv = _make_conv(
        db, workspace_a.id, status="archived", assigned_user_id=user_a.id, ai_enabled=False
    )
    db.commit()

    resp = client_a.post(f"/conversations/{conv.id}/return-to-ai")
    assert resp.status_code == 409


def test_take_over_http_cross_workspace_404(db: Session, workspace_b: Workspace, client_a):
    conv = _make_conv(db, workspace_b.id)
    db.commit()

    resp = client_a.post(f"/conversations/{conv.id}/take-over")
    assert resp.status_code == 404


# ── Auto-reply interaction ─────────────────────────────────────────────────────

def test_after_take_over_no_auto_reply(db: Session, workspace_a: Workspace, user_a):
    plan = _make_plan(db)
    _make_subscription(db, workspace_a, plan)
    _make_counter(db, workspace_a.id)
    agent = _make_ai_agent(db, workspace_a.id)
    conv = _make_conv(db, workspace_a.id, agent)
    db.commit()

    # Human takes over.
    take_over_conversation(db, workspace_a.id, conv.id, user_a.id)
    db.refresh(conv)

    # Customer sends a message — should NOT trigger auto-reply.
    data = ConversationMessageCreate(
        direction="inbound", sender_type="customer", content="Olá"
    )
    with patch(_LLM_PATCH, return_value=_mock_llm()) as mock_llm:
        create_message(db, workspace_a.id, conv.id, user_a.id, data)

    mock_llm.assert_not_called()
    assert _count_agent_replies(db, conv.id) == 0


def test_after_return_to_ai_auto_reply_resumes(db: Session, workspace_a: Workspace, user_a):
    plan = _make_plan(db)
    _make_subscription(db, workspace_a, plan)
    _make_counter(db, workspace_a.id)
    agent = _make_ai_agent(db, workspace_a.id)
    conv = _make_conv(db, workspace_a.id, agent, assigned_user_id=user_a.id, ai_enabled=False)
    db.commit()

    # Return to AI.
    return_to_ai(db, workspace_a.id, conv.id)
    db.refresh(conv)

    # Customer sends a message — should trigger auto-reply.
    data = ConversationMessageCreate(
        direction="inbound", sender_type="customer", content="Preciso de ajuda"
    )
    with patch(_LLM_PATCH, return_value=_mock_llm()):
        create_message(db, workspace_a.id, conv.id, user_a.id, data)

    assert _count_agent_replies(db, conv.id) == 1
