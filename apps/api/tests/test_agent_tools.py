"""
Tests for AgentTool CRUD (Fase 4 of the tool-calling PRD): the
/agents/{id}/tools/http endpoints, plan gating, and the service-level
helpers that turn a row into an LLM tool schema / dispatch entry.

Also covers tool_type="request_human" (request-human-tool-prd.md): the
/agents/{id}/tools/request-human endpoints (no plan gate — available on
every plan) and execute_request_human_tool's simulation/real/idempotent/
notification behavior.
"""

import uuid
from unittest.mock import patch

import httpx
import pytest

from app.models.contact import Contact
from app.models.conversation import Conversation
from app.services.agent_tool_service import (
    build_tool_dispatch,
    build_tool_schema,
    execute_http_tool,
    execute_request_human_tool,
    validate_http_tool_config,
)
from app.services.email_service import FakeEmailService, override_email_service, reset_email_service

# api.example.com doesn't reliably resolve in a sandboxed/offline test run —
# same problem the pipeline webhook tests solve by faking socket.getaddrinfo
# instead of depending on real DNS. 93.184.216.34 is example.com's real IP,
# used here just so it's an unambiguously public address.
_PUBLIC_DNS_PATCH = patch(
    "socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]
)


def _agent_payload(ai_model_id: uuid.UUID, **kwargs) -> dict:
    defaults = {
        "name": "Agente com Tools",
        "system_prompt": "You are a helpful agent.",
        "ai_model_id": str(ai_model_id),
        "temperature": 0.7,
    }
    defaults.update(kwargs)
    return defaults


def _create_agent(client, ai_model, name: str = "Agente com Tools") -> str:
    r = client.post("/agents", json=_agent_payload(ai_model.id, name=name))
    assert r.status_code == 201
    return r.json()["id"]


def _http_tool_payload(**overrides) -> dict:
    defaults = {
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
    defaults.update(overrides)
    return defaults


# ── CRUD + plan gating (via HTTP) ────────────────────────────────────────────────


def test_create_http_tool_requires_scale_plan(client_a, subscription_a, ai_model):
    """subscription_a defaults to starter — http_tools is Scale+."""
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload())
    assert r.status_code == 402


def test_create_http_tool_succeeds_on_scale_plan(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with _PUBLIC_DNS_PATCH:
        r = client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "consultar_cep"
    assert body["tool_type"] == "http_request"
    assert body["is_enabled"] is True
    assert body["config"]["url"] == "https://api.example.com/cep"


def test_create_http_tool_rejects_private_url(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    payload = _http_tool_payload(config={
        "method": "GET", "url": "http://127.0.0.1/internal", "headers": {}, "timeout_seconds": 8,
    })
    r = client_a.post(f"/agents/{agent_id}/tools/http", json=payload)
    assert r.status_code == 400


def test_create_duplicate_tool_name_returns_409(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with _PUBLIC_DNS_PATCH:
        client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload())
        r = client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload())
    assert r.status_code == 409


def test_list_http_tools(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with _PUBLIC_DNS_PATCH:
        client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload())
    r = client_a.get(f"/agents/{agent_id}/tools/http")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_update_http_tool_toggle_disabled(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with _PUBLIC_DNS_PATCH:
        created = client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload()).json()
    r = client_a.patch(
        f"/agents/{agent_id}/tools/http/{created['id']}", json={"is_enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False


def test_update_http_tool_rejects_private_url(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with _PUBLIC_DNS_PATCH:
        created = client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload()).json()
    r = client_a.patch(
        f"/agents/{agent_id}/tools/http/{created['id']}",
        json={"config": {"method": "GET", "url": "http://169.254.169.254/", "headers": {}}},
    )
    assert r.status_code == 400


def test_delete_http_tool(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with _PUBLIC_DNS_PATCH:
        created = client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload()).json()
    r = client_a.delete(f"/agents/{agent_id}/tools/http/{created['id']}")
    assert r.status_code == 204
    assert client_a.get(f"/agents/{agent_id}/tools/http").json() == []


def test_tools_are_isolated_per_agent(client_a, scale_subscription_a, ai_model):
    agent_id_1 = _create_agent(client_a, ai_model)
    agent_id_2 = _create_agent(client_a, ai_model, name="Outro agente")
    with _PUBLIC_DNS_PATCH:
        client_a.post(f"/agents/{agent_id_1}/tools/http", json=_http_tool_payload())
    assert client_a.get(f"/agents/{agent_id_2}/tools/http").json() == []


# ── Service-level: schema building + dispatch + HTTP execution ─────────────────


_SAMPLE_CONFIG = {
    "method": "GET", "url": "https://api.example.com/cep", "headers": {}, "timeout_seconds": 8,
}


class _FakeTool:
    def __init__(
        self, tool_type="http_request", name="consultar_cep", description="Consulta CEP",
        config=None,
    ):
        self.tool_type = tool_type
        self.name = name
        self.description = description
        self.config = config or _SAMPLE_CONFIG


def test_build_tool_schema_http_request():
    schema = build_tool_schema(_FakeTool())
    assert schema["name"] == "consultar_cep"
    assert schema["description"] == "Consulta CEP"
    assert "query_params" in schema["input_schema"]["properties"]
    assert "body" in schema["input_schema"]["properties"]


def test_build_tool_schema_unknown_type_raises():
    with pytest.raises(ValueError):
        build_tool_schema(_FakeTool(tool_type="something_else"))


def test_build_tool_schema_url_placeholders_become_required_properties():
    tool = _FakeTool(config={
        "method": "GET", "url": "https://api.example.com/cep/{cep}",
        "headers": {}, "timeout_seconds": 8,
    })
    schema = build_tool_schema(tool)
    assert "cep" in schema["input_schema"]["properties"]
    assert schema["input_schema"]["properties"]["cep"]["type"] == "string"
    assert schema["input_schema"]["required"] == ["cep"]


def test_build_tool_schema_multiple_url_placeholders():
    tool = _FakeTool(config={
        "method": "GET", "url": "https://api.example.com/{resource}/{id}",
        "headers": {}, "timeout_seconds": 8,
    })
    schema = build_tool_schema(tool)
    assert set(schema["input_schema"]["required"]) == {"resource", "id"}


def test_build_tool_schema_no_placeholders_has_no_required():
    schema = build_tool_schema(_FakeTool())  # _SAMPLE_CONFIG has no {placeholder}
    assert "required" not in schema["input_schema"]


def test_build_tool_dispatch_maps_name_to_executor():
    dispatch = build_tool_dispatch([_FakeTool()])
    assert "consultar_cep" in dispatch
    assert callable(dispatch["consultar_cep"])


@patch("app.services.agent_tool_service.httpx.request")
def test_execute_http_tool_success(mock_request):
    mock_request.return_value = httpx.Response(200, text='{"logradouro": "Rua X"}')
    with _PUBLIC_DNS_PATCH:
        result = execute_http_tool(_SAMPLE_CONFIG, {"query_params": {"cep": "01001000"}})

    assert '"status_code": 200' in result
    call_url = mock_request.call_args.args[1]
    assert "cep=01001000" in call_url


@patch("app.services.agent_tool_service.httpx.request")
def test_execute_http_tool_substitutes_url_placeholder(mock_request):
    mock_request.return_value = httpx.Response(200, text='{"logradouro": "Praça da Sé"}')
    config = {**_SAMPLE_CONFIG, "url": "https://api.example.com/cep/{cep}"}
    with _PUBLIC_DNS_PATCH:
        execute_http_tool(config, {"cep": "01001000"})

    call_url = mock_request.call_args.args[1]
    assert call_url == "https://api.example.com/cep/01001000"


def test_execute_http_tool_missing_url_placeholder_raises():
    config = {**_SAMPLE_CONFIG, "url": "https://api.example.com/cep/{cep}"}
    with pytest.raises(ValueError, match="cep"):
        execute_http_tool(config, {})


@patch("app.services.agent_tool_service.httpx.request")
def test_execute_http_tool_url_placeholder_cannot_escape_path(mock_request):
    # A model-controlled value trying to break out of the path (path traversal,
    # or a "//evil.com" host-injection attempt) must come back fully encoded —
    # the request must still go to api.example.com, never anywhere else.
    mock_request.return_value = httpx.Response(200, text="ok")
    config = {**_SAMPLE_CONFIG, "url": "https://api.example.com/items/{id}"}
    with _PUBLIC_DNS_PATCH:
        execute_http_tool(config, {"id": "../../etc/passwd"})

    call_url = mock_request.call_args.args[1]
    assert call_url.startswith("https://api.example.com/items/")
    # The "/" separators are percent-encoded (%2F), so the payload is one opaque
    # path segment — it can never be interpreted as ../.. traversal by anything
    # parsing the URL, even though the literal dots themselves aren't escaped
    # (unreserved characters per RFC 3986 — quote() never encodes them).
    assert "/etc/passwd" not in call_url
    assert call_url.count("/") == 4  # scheme's //, host/, /items/, nothing beyond


@patch("app.services.agent_tool_service.httpx.request")
def test_execute_http_tool_url_placeholder_cannot_inject_host(mock_request):
    mock_request.return_value = httpx.Response(200, text="ok")
    config = {**_SAMPLE_CONFIG, "url": "https://api.example.com/items/{id}"}
    with _PUBLIC_DNS_PATCH:
        execute_http_tool(config, {"id": "x/../../@evil.com/"})

    call_url = mock_request.call_args.args[1]
    assert call_url.startswith("https://api.example.com/items/")
    assert "evil.com" in call_url  # present, but only as an encoded path segment...
    assert "://evil.com" not in call_url  # ...never as a scheme+host


@patch("app.services.agent_tool_service.httpx.request")
def test_execute_http_tool_sends_json_body_for_post(mock_request):
    mock_request.return_value = httpx.Response(201, text="ok")
    config = {**_SAMPLE_CONFIG, "method": "POST", "url": "https://api.example.com/orders"}
    with _PUBLIC_DNS_PATCH:
        execute_http_tool(config, {"body": {"item": "x"}})

    call_kwargs = mock_request.call_args.kwargs
    assert call_kwargs["json"] == {"item": "x"}


def test_execute_http_tool_rejects_private_url_even_if_saved_public_url_was_rebound():
    # Simulates DNS rebinding: config.url looks fine but re-validation must still run.
    config = {"method": "GET", "url": "http://127.0.0.1/", "headers": {}, "timeout_seconds": 8}
    with pytest.raises(Exception):
        execute_http_tool(config, {})


@patch("app.services.agent_tool_service.httpx.request")
def test_execute_http_tool_truncates_long_response(mock_request):
    mock_request.return_value = httpx.Response(200, text="x" * 10_000)
    with _PUBLIC_DNS_PATCH:
        result = execute_http_tool(_SAMPLE_CONFIG, {})
    assert len(result) < 5000


# ── request_human: CRUD (no plan gate) ──────────────────────────────────────────


def _request_human_payload(**overrides) -> dict:
    defaults = {
        "tool_type": "request_human",
        "name": "solicitar_humano",
        "description": "Aciona quando o cliente pedir reembolso ou reclamar.",
        "config": {},
    }
    defaults.update(overrides)
    return defaults


def test_create_request_human_tool_succeeds_on_starter_plan(client_a, subscription_a, ai_model):
    """subscription_a defaults to starter — request_human has no plan gate, unlike http_tools."""
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(f"/agents/{agent_id}/tools/request-human", json=_request_human_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["tool_type"] == "request_human"
    assert body["config"] == {}


def test_create_request_human_tool_rejects_wrong_tool_type(client_a, subscription_a, ai_model):
    """Posting an http_request body to /tools/request-human must not silently
    create an HTTP tool bypassing the http_tools plan gate."""
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/request-human", json=_http_tool_payload()
    )
    assert r.status_code == 400


def test_create_http_tool_via_request_human_route_rejected(
    client_a, scale_subscription_a, ai_model
):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(f"/agents/{agent_id}/tools/http", json=_request_human_payload())
    assert r.status_code == 400


def test_update_request_human_tool_toggle_disabled(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    created = client_a.post(
        f"/agents/{agent_id}/tools/request-human", json=_request_human_payload()
    ).json()
    r = client_a.patch(
        f"/agents/{agent_id}/tools/request-human/{created['id']}", json={"is_enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False


def test_delete_request_human_tool(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    created = client_a.post(
        f"/agents/{agent_id}/tools/request-human", json=_request_human_payload()
    ).json()
    r = client_a.delete(f"/agents/{agent_id}/tools/request-human/{created['id']}")
    assert r.status_code == 204
    assert client_a.get(f"/agents/{agent_id}/tools/http").json() == []


def test_list_tools_returns_both_types(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with _PUBLIC_DNS_PATCH:
        client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload())
    client_a.post(f"/agents/{agent_id}/tools/request-human", json=_request_human_payload())
    tool_types = {t["tool_type"] for t in client_a.get(f"/agents/{agent_id}/tools/http").json()}
    assert tool_types == {"http_request", "request_human"}


# ── request_human: service-level schema/dispatch/execution ─────────────────────


class _FakeRequestHumanTool(_FakeTool):
    def __init__(self, name="solicitar_humano", description="Aciona em reembolsos."):
        super().__init__(tool_type="request_human", name=name, description=description, config={})


def test_build_tool_schema_request_human():
    schema = build_tool_schema(_FakeRequestHumanTool())
    assert schema["name"] == "solicitar_humano"
    assert schema["input_schema"]["required"] == ["reason"]
    assert "reason" in schema["input_schema"]["properties"]


def test_execute_request_human_tool_simulation_mode_when_no_conversation():
    result = execute_request_human_tool(
        db=None, workspace_id=None, conversation=None, reason="Cliente quer reembolso."
    )
    assert "Simulação" in result
    assert "reembolso" in result


@pytest.fixture()
def fake_email() -> FakeEmailService:
    svc = FakeEmailService()
    override_email_service(svc)
    yield svc
    reset_email_service()


def test_execute_request_human_tool_pauses_ai_and_sets_reason(
    db, workspace_a, fake_email
):
    contact = Contact(workspace_id=workspace_a.id, name="Cliente Teste", phone="+5511999999999")
    db.add(contact)
    db.flush()
    conv = Conversation(
        workspace_id=workspace_a.id, contact_id=contact.id,
        channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_request_human_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv, reason="Cliente quer reembolso."
    )

    assert "sucesso" in result.lower()
    assert conv.ai_enabled is False
    assert conv.handoff_reason == "Cliente quer reembolso."
    # user_a (workspace_a's owner) must have received the notification.
    assert len(fake_email.sent) == 1
    assert "Cliente Teste" in fake_email.sent[0]["html"]
    assert "Cliente quer reembolso." in fake_email.sent[0]["html"]


def test_execute_request_human_tool_is_idempotent_within_a_turn(db, workspace_a, fake_email):
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    execute_request_human_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv, reason="Primeiro motivo."
    )
    second = execute_request_human_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv, reason="Segundo motivo."
    )

    assert "já" in second.lower()
    assert conv.handoff_reason == "Primeiro motivo."  # unchanged by the second call
    assert len(fake_email.sent) == 1  # no duplicate notification


def test_execute_request_human_tool_notify_failure_does_not_raise(db, workspace_a, fake_email):
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    with patch(
        "app.services.email_service.FakeEmailService.send", side_effect=RuntimeError("boom")
    ):
        result = execute_request_human_tool(
            db=db, workspace_id=workspace_a.id, conversation=conv, reason="Motivo qualquer."
        )

    # The handoff itself must still succeed even though the notification blew up.
    assert conv.ai_enabled is False
    assert "sucesso" in result.lower()


def test_build_tool_dispatch_request_human_wires_context():
    calls = []

    def _fake_execute(**kwargs):
        calls.append(kwargs)
        return "ok"

    with patch("app.services.agent_tool_service.execute_request_human_tool", _fake_execute):
        dispatch = build_tool_dispatch(
            [_FakeRequestHumanTool()], db="db-sentinel", workspace_id="ws-sentinel",
            conversation="conv-sentinel",
        )
        dispatch["solicitar_humano"]({"reason": "Teste"})

    assert calls == [{
        "db": "db-sentinel", "workspace_id": "ws-sentinel",
        "conversation": "conv-sentinel", "reason": "Teste",
    }]


# ── http_request: structured query params + path descriptions (UX PRD) ─────────


def test_build_tool_schema_backward_compatible_without_new_fields():
    """A tool saved before this PRD has no path_param_descriptions/query_params
    keys at all — build_tool_schema must fall back to the original generic
    behavior, not KeyError."""
    schema = build_tool_schema(_FakeTool())  # _SAMPLE_CONFIG has neither key
    assert schema["input_schema"]["properties"]["query_params"] == {
        "type": "object",
        "description": "Optional query string parameters to add to the request.",
    }


def test_build_tool_schema_uses_custom_path_param_description():
    tool = _FakeTool(config={
        "method": "GET", "url": "https://api.example.com/cep/{cep}", "headers": {},
        "timeout_seconds": 8, "path_param_descriptions": {"cep": "CEP no formato 00000-000."},
    })
    schema = build_tool_schema(tool)
    assert schema["input_schema"]["properties"]["cep"]["description"] == "CEP no formato 00000-000."


def test_build_tool_schema_structured_query_params():
    tool = _FakeTool(config={
        **_SAMPLE_CONFIG,
        "query_params": [
            {"name": "formato", "description": "json ou xml", "required": True},
            {"name": "pagina", "description": "Número da página", "required": False},
        ],
    })
    schema = build_tool_schema(tool)
    qp_schema = schema["input_schema"]["properties"]["query_params"]
    assert set(qp_schema["properties"]) == {"formato", "pagina"}
    assert qp_schema["properties"]["formato"]["description"] == "json ou xml"
    assert qp_schema["required"] == ["formato"]


@patch("app.services.agent_tool_service.httpx.request")
def test_execute_http_tool_still_works_with_structured_query_params_config(mock_request):
    """query_params in config only shapes the schema shown to the model —
    execution still reads input_["query_params"] as a plain dict, unchanged."""
    mock_request.return_value = httpx.Response(200, text="ok")
    config = {
        **_SAMPLE_CONFIG,
        "query_params": [{"name": "formato", "description": "", "required": True}],
    }
    with _PUBLIC_DNS_PATCH:
        execute_http_tool(config, {"query_params": {"formato": "json"}})
    call_url = mock_request.call_args.args[1]
    assert "formato=json" in call_url


# ── http_request: "Validar Configuração" (test before saving) ──────────────────


@patch("app.services.agent_tool_service.httpx.request")
def test_validate_http_tool_config_success(mock_request):
    mock_request.return_value = httpx.Response(200, text='{"logradouro": "Praça da Sé"}')
    with _PUBLIC_DNS_PATCH:
        result = validate_http_tool_config(_SAMPLE_CONFIG, {"query_params": {"cep": "01001000"}})
    assert result["ok"] is True
    assert result["status_code"] == 200
    assert "Praça da Sé" in result["body"]


def test_validate_http_tool_config_reports_failure_instead_of_raising():
    config = {**_SAMPLE_CONFIG, "url": "https://api.example.com/cep/{cep}"}
    result = validate_http_tool_config(config, {})  # missing required {cep}
    assert result["ok"] is False
    assert "error" in result
    assert result["error"]


def test_validate_http_tool_config_rejects_private_url():
    config = {"method": "GET", "url": "http://127.0.0.1/", "headers": {}, "timeout_seconds": 8}
    result = validate_http_tool_config(config, {})
    assert result["ok"] is False


def test_validate_endpoint_requires_scale_plan(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/http/test",
        json={"config": _SAMPLE_CONFIG, "sample_input": {}},
    )
    assert r.status_code == 402


def test_validate_endpoint_succeeds_on_scale_plan(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    with patch("app.services.agent_tool_service.httpx.request") as mock_request, _PUBLIC_DNS_PATCH:
        mock_request.return_value = httpx.Response(200, text="ok")
        r = client_a.post(
            f"/agents/{agent_id}/tools/http/test",
            json={"config": _SAMPLE_CONFIG, "sample_input": {}},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["status_code"] == 200


def test_create_http_tool_with_structured_query_params_via_api(
    client_a, scale_subscription_a, ai_model
):
    agent_id = _create_agent(client_a, ai_model)
    payload = _http_tool_payload(config={
        "method": "GET", "url": "https://api.example.com/cep", "headers": {},
        "timeout_seconds": 8,
        "query_params": [{"name": "formato", "description": "json ou xml", "required": True}],
    })
    with _PUBLIC_DNS_PATCH:
        r = client_a.post(f"/agents/{agent_id}/tools/http", json=payload)
    assert r.status_code == 201
    assert r.json()["config"]["query_params"] == [
        {"name": "formato", "description": "json ou xml", "required": True}
    ]
