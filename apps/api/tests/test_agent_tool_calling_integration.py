"""
End-to-end integration tests proving the tool-calling wiring actually works
through the real call sites — not just the isolated unit tests in
test_agent_llm_executor.py / test_agent_tools.py. Drives a real HTTP tool
(created via the API) through a real agent turn with a mocked LLM that
requests the tool, then verifies the loop, the audit rows, and the credits.
"""

import uuid
from unittest.mock import patch

import httpx
import pytest

from app.llm.schemas import LLMResponse
from app.models.agent_tool_call import AgentToolCall
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.conversation_agent_reply_service import generate_conversation_agent_reply
from app.services.email_service import FakeEmailService, override_email_service, reset_email_service

_PUBLIC_DNS_PATCH = patch(
    "socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]
)


@pytest.fixture()
def executable_ai_model(db) -> AiModel:
    """Both call sites gate on model_name — the generic `ai_model` fixture's
    generated name ("test-model-xxxx-v1") isn't in either allowlist, so
    these tests need a model whose name is actually executable."""
    provider = AiModelProvider(id=uuid.uuid4(), code="anthropic", name="Anthropic", is_active=True)
    db.add(provider)
    db.flush()
    model = AiModel(
        id=uuid.uuid4(),
        provider_id=provider.id,
        code="claude-sonnet-4-6",
        display_name="Claude Sonnet",
        model_name="claude-sonnet-4-6",
        credits_per_message=1,
        min_plan_code="starter",
        is_default=True,
        is_active=True,
        sort_order=1,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def _agent_payload(ai_model_id: uuid.UUID) -> dict:
    return {
        "name": "Agente com CEP",
        "system_prompt": "Você ajuda a consultar CEPs.",
        "ai_model_id": str(ai_model_id),
        "temperature": 0.7,
    }


def _http_tool_payload() -> dict:
    return {
        "tool_type": "http_request",
        "name": "consultar_cep",
        "description": "Consulta um CEP e retorna o endereço correspondente.",
        "config": {
            "method": "GET",
            "url": "https://api.example.com/cep",
            "headers": {},
            "timeout_seconds": 8,
        },
    }


def _tool_use_response() -> LLMResponse:
    return LLMResponse(
        content="",
        input_tokens=20,
        output_tokens=8,
        duration_ms=150,
        stop_reason="tool_use",
        content_blocks=[{
            "type": "tool_use", "id": "toolu_1", "name": "consultar_cep",
            "input": {"query_params": {"cep": "01001000"}},
        }],
    )


def _final_response() -> LLMResponse:
    return LLMResponse(
        content="O CEP 01001000 corresponde à Praça da Sé, São Paulo.",
        input_tokens=15,
        output_tokens=12,
        duration_ms=120,
        stop_reason="end_turn",
        content_blocks=[{
            "type": "text", "text": "O CEP 01001000 corresponde à Praça da Sé, São Paulo.",
        }],
    )


# ── Playground / test path (via the real HTTP endpoint) ────────────────────────


def test_playground_test_endpoint_drives_full_tool_calling_loop(
    client_a, scale_subscription_a, executable_ai_model
):
    agent = client_a.post("/agents", json=_agent_payload(executable_ai_model.id)).json()
    with _PUBLIC_DNS_PATCH:
        client_a.post(f"/agents/{agent['id']}/tools/http", json=_http_tool_payload())
    client_a.patch(f"/agents/{agent['id']}/status", json={"status": "active"})

    with patch("app.llm.client.complete", side_effect=[_tool_use_response(), _final_response()]), \
         patch("app.services.agent_tool_service.httpx.request") as mock_http, \
         _PUBLIC_DNS_PATCH:
        mock_http.return_value = httpx.Response(200, text='{"logradouro": "Praça da Sé"}')
        r = client_a.post(
            f"/agents/{agent['id']}/test",
            json={"message": "Qual o endereço do CEP 01001000?"},
        )

    assert r.status_code == 200
    body = r.json()
    assert "Praça da Sé" in body["reply"]
    # Credits/tokens must reflect BOTH round-trips, not just the final one.
    assert body["input_tokens"] == 20 + 15
    assert body["output_tokens"] == 8 + 12
    mock_http.assert_called_once()
    call_url = mock_http.call_args.args[1]
    assert "cep=01001000" in call_url


# ── Production reply path (direct service call, matching existing test style) ──


def test_conversation_reply_drives_full_tool_calling_loop(
    db, client_a, scale_subscription_a, executable_ai_model, workspace_a, user_a
):
    agent = client_a.post("/agents", json=_agent_payload(executable_ai_model.id)).json()
    with _PUBLIC_DNS_PATCH:
        client_a.post(f"/agents/{agent['id']}/tools/http", json=_http_tool_payload())
    client_a.patch(f"/agents/{agent['id']}/status", json={"status": "active"})

    contact = Contact(workspace_id=workspace_a.id, name="Cliente", phone="+5511999999999")
    db.add(contact)
    db.flush()

    conv = Conversation(
        workspace_id=workspace_a.id,
        contact_id=contact.id,
        agent_id=uuid.UUID(agent["id"]),
        channel_type="internal",
        status="open",
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()

    trigger = ConversationMessage(
        workspace_id=workspace_a.id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content="Qual o endereço do CEP 01001000?",
        content_type="text",
    )
    db.add(trigger)
    db.commit()
    db.refresh(conv)
    db.refresh(trigger)

    with patch("app.llm.client.complete", side_effect=[_tool_use_response(), _final_response()]), \
         patch("app.services.agent_tool_service.httpx.request") as mock_http, \
         _PUBLIC_DNS_PATCH:
        mock_http.return_value = httpx.Response(200, text='{"logradouro": "Praça da Sé"}')
        run = generate_conversation_agent_reply(db, workspace_a.id, conv, trigger)

    assert run is not None
    assert run.status == "success"
    assert run.input_tokens == 20 + 15
    assert run.output_tokens == 8 + 12
    mock_http.assert_called_once()

    tool_call_rows = (
        db.query(AgentToolCall)
        .filter(AgentToolCall.conversation_agent_run_id == run.id)
        .order_by(AgentToolCall.call_index)
        .all()
    )
    assert len(tool_call_rows) == 2
    assert tool_call_rows[0].tool_calls[0]["tool_name"] == "consultar_cep"
    assert tool_call_rows[0].tool_calls[0]["status"] == "success"
    assert tool_call_rows[1].tool_calls == []  # final round-trip made no tool call


# ── request_human tool — full conversation reply loop, ungated by plan ─────────


def _request_human_tool_payload() -> dict:
    return {
        "tool_type": "request_human",
        "name": "solicitar_humano",
        "description": "Aciona quando o cliente pedir reembolso.",
        "config": {},
    }


def _request_human_tool_use_response() -> LLMResponse:
    return LLMResponse(
        content="",
        input_tokens=18,
        output_tokens=6,
        duration_ms=100,
        stop_reason="tool_use",
        content_blocks=[{
            "type": "tool_use", "id": "toolu_2", "name": "solicitar_humano",
            "input": {"reason": "Cliente pede reembolso por produto com defeito."},
        }],
    )


def _handoff_final_response() -> LLMResponse:
    return LLMResponse(
        content="Vou te conectar com nossa equipe, só um momento.",
        input_tokens=10,
        output_tokens=9,
        duration_ms=90,
        stop_reason="end_turn",
        content_blocks=[{
            "type": "text", "text": "Vou te conectar com nossa equipe, só um momento.",
        }],
    )


@pytest.fixture()
def fake_email() -> FakeEmailService:
    svc = FakeEmailService()
    override_email_service(svc)
    yield svc
    reset_email_service()


def test_conversation_reply_request_human_pauses_ai_on_starter_plan(
    db, client_a, subscription_a, executable_ai_model, workspace_a, user_a, fake_email
):
    """subscription_a defaults to starter — request_human must still work, unlike http_tools."""
    agent = client_a.post("/agents", json=_agent_payload(executable_ai_model.id)).json()
    client_a.post(f"/agents/{agent['id']}/tools/request-human", json=_request_human_tool_payload())
    client_a.patch(f"/agents/{agent['id']}/status", json={"status": "active"})

    contact = Contact(workspace_id=workspace_a.id, name="Cliente", phone="+5511988887777")
    db.add(contact)
    db.flush()

    conv = Conversation(
        workspace_id=workspace_a.id,
        contact_id=contact.id,
        agent_id=uuid.UUID(agent["id"]),
        channel_type="internal",
        status="open",
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()

    trigger = ConversationMessage(
        workspace_id=workspace_a.id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content="Quero reembolso, chegou com defeito.",
        content_type="text",
    )
    db.add(trigger)
    db.commit()
    db.refresh(conv)
    db.refresh(trigger)

    with patch(
        "app.llm.client.complete",
        side_effect=[_request_human_tool_use_response(), _handoff_final_response()],
    ):
        run = generate_conversation_agent_reply(db, workspace_a.id, conv, trigger)

    assert run is not None
    assert run.status == "success"

    db.refresh(conv)
    assert conv.ai_enabled is False
    assert conv.handoff_reason == "Cliente pede reembolso por produto com defeito."
    assert len(fake_email.sent) == 1


# ── mark_resolved tool — full conversation reply loop, ungated by plan ─────────


def _mark_resolved_tool_payload() -> dict:
    return {
        "tool_type": "mark_resolved",
        "name": "marcar_resolvido",
        "description": "Aciona quando o cliente confirma que o problema foi resolvido.",
        "config": {},
    }


def _mark_resolved_tool_use_response() -> LLMResponse:
    return LLMResponse(
        content="",
        input_tokens=15,
        output_tokens=5,
        duration_ms=90,
        stop_reason="tool_use",
        content_blocks=[{
            "type": "tool_use", "id": "toolu_3", "name": "marcar_resolvido",
            "input": {"resolution_summary": "Cliente confirmou recebimento do pedido."},
        }],
    )


def _resolved_final_response() -> LLMResponse:
    return LLMResponse(
        content="Que bom que deu tudo certo! Qualquer coisa, é só chamar.",
        input_tokens=8,
        output_tokens=10,
        duration_ms=80,
        stop_reason="end_turn",
        content_blocks=[{
            "type": "text", "text": "Que bom que deu tudo certo! Qualquer coisa, é só chamar.",
        }],
    )


def test_conversation_reply_mark_resolved_on_starter_plan(
    db, client_a, subscription_a, executable_ai_model, workspace_a, user_a
):
    """subscription_a defaults to starter — mark_resolved must still work, unlike http_tools."""
    agent = client_a.post("/agents", json=_agent_payload(executable_ai_model.id)).json()
    client_a.post(f"/agents/{agent['id']}/tools/mark-resolved", json=_mark_resolved_tool_payload())
    client_a.patch(f"/agents/{agent['id']}/status", json={"status": "active"})

    contact = Contact(workspace_id=workspace_a.id, name="Cliente", phone="+5511977776666")
    db.add(contact)
    db.flush()

    conv = Conversation(
        workspace_id=workspace_a.id,
        contact_id=contact.id,
        agent_id=uuid.UUID(agent["id"]),
        channel_type="internal",
        status="open",
        ai_enabled=True,
    )
    db.add(conv)
    db.flush()

    trigger = ConversationMessage(
        workspace_id=workspace_a.id,
        conversation_id=conv.id,
        direction="inbound",
        sender_type="customer",
        content="Recebi o pedido certinho, obrigado!",
        content_type="text",
    )
    db.add(trigger)
    db.commit()
    db.refresh(conv)
    db.refresh(trigger)

    with patch(
        "app.llm.client.complete",
        side_effect=[_mark_resolved_tool_use_response(), _resolved_final_response()],
    ):
        run = generate_conversation_agent_reply(db, workspace_a.id, conv, trigger)

    assert run is not None
    assert run.status == "success"

    db.refresh(conv)
    assert conv.status == "resolved"
    assert conv.resolution_summary == "Cliente confirmou recebimento do pedido."
    # Must not touch ai_enabled/assigned_user_id — same end state as the
    # manual "Resolvida" dropdown in the Inbox.
    assert conv.ai_enabled is True
    assert conv.assigned_user_id is None
