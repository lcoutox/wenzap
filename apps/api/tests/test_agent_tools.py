"""
Tests for AgentTool CRUD (Fase 4 of the tool-calling PRD): the
/agents/{id}/tools/http endpoints, plan gating, and the service-level
helpers that turn a row into an LLM tool schema / dispatch entry.
"""

import uuid
from unittest.mock import patch

import httpx
import pytest

from app.services.agent_tool_service import (
    build_tool_dispatch,
    build_tool_schema,
    execute_http_tool,
)

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
