"""
Tests for the Anthropic provider layer (app/llm/providers/anthropic.py).

No existing test exercised this file directly — every other test mocks one
layer up (llm_client.complete). These tests mock the Anthropic SDK client
itself to verify request shaping (tools/tool_choice passthrough) and
response mapping (content_blocks, stop_reason, error classification),
which is exactly what Fase 1 of the tool-calling PRD added.
"""

from unittest.mock import MagicMock, patch

import anthropic as anthropic_sdk
import pytest

from app.llm.providers import anthropic as provider
from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest


def _request(**overrides) -> LLMRequest:
    defaults = dict(
        model_name="claude-haiku-4-5",
        system="You are a helpful agent.",
        messages=[LLMMessage(role="user", content="Oi")],
        temperature=0.7,
    )
    defaults.update(overrides)
    return LLMRequest(**defaults)


def _sdk_response(content_blocks: list[dict], stop_reason: str = "end_turn"):
    """Build a fake Anthropic SDK response whose content blocks .model_dump() as given."""
    blocks = []
    for b in content_blocks:
        block = MagicMock()
        block.model_dump.return_value = b
        blocks.append(block)
    resp = MagicMock()
    resp.content = blocks
    resp.stop_reason = stop_reason
    resp.usage.input_tokens = 10
    resp.usage.output_tokens = 5
    return resp


@patch("app.llm.providers.anthropic.settings")
def test_complete_plain_text_response(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    resp = _sdk_response([{"type": "text", "text": "Olá!"}])
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = resp
        result = provider.complete(_request())

    assert result.content == "Olá!"
    assert result.stop_reason == "end_turn"
    assert result.content_blocks == [{"type": "text", "text": "Olá!"}]
    assert result.input_tokens == 10
    assert result.output_tokens == 5


@patch("app.llm.providers.anthropic.settings")
def test_complete_does_not_pass_tools_when_absent(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    resp = _sdk_response([{"type": "text", "text": "Oi"}])
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = resp
        provider.complete(_request())
        call_kwargs = MockClient.return_value.messages.create.call_args.kwargs

    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs


@patch("app.llm.providers.anthropic.settings")
def test_complete_passes_tools_and_tool_choice_when_present(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    tools = [{"name": "http_request", "description": "Call an HTTP endpoint.", "input_schema": {}}]
    resp = _sdk_response([{"type": "text", "text": "Oi"}])
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = resp
        provider.complete(_request(tools=tools, tool_choice={"type": "auto"}))
        call_kwargs = MockClient.return_value.messages.create.call_args.kwargs

    assert call_kwargs["tools"] == tools
    assert call_kwargs["tool_choice"] == {"type": "auto"}


@patch("app.llm.providers.anthropic.settings")
def test_complete_tool_use_response_has_no_text(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    tool_use_block = {"type": "tool_use", "id": "toolu_1", "name": "http_request", "input": {"url": "https://x"}}
    resp = _sdk_response([tool_use_block], stop_reason="tool_use")
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = resp
        result = provider.complete(_request())

    assert result.content == ""
    assert result.stop_reason == "tool_use"
    assert result.content_blocks == [tool_use_block]


@patch("app.llm.providers.anthropic.settings")
def test_complete_mixed_text_and_tool_use_joins_text_only(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    blocks = [
        {"type": "text", "text": "Deixa eu checar isso."},
        {"type": "tool_use", "id": "toolu_2", "name": "http_request", "input": {}},
    ]
    resp = _sdk_response(blocks, stop_reason="tool_use")
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = resp
        result = provider.complete(_request())

    assert result.content == "Deixa eu checar isso."
    assert result.content_blocks == blocks


@patch("app.llm.providers.anthropic.settings")
def test_auth_error_is_not_transient(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = anthropic_sdk.AuthenticationError(
            "bad key", response=MagicMock(), body=None
        )
        with pytest.raises(LLMProviderError) as exc_info:
            provider.complete(_request())

    assert exc_info.value.auth_error is True
    assert exc_info.value.transient is False
    assert exc_info.value.provider == "anthropic"


@patch("app.llm.providers.anthropic.settings")
def test_rate_limit_error_is_transient(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = anthropic_sdk.RateLimitError(
            "slow down", response=MagicMock(), body=None
        )
        with pytest.raises(LLMProviderError) as exc_info:
            provider.complete(_request())

    assert exc_info.value.auth_error is False
    assert exc_info.value.transient is True


@patch("app.llm.providers.anthropic.settings")
def test_connection_error_is_transient(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = anthropic_sdk.APIConnectionError(
            request=MagicMock()
        )
        with pytest.raises(LLMProviderError) as exc_info:
            provider.complete(_request())

    assert exc_info.value.transient is True


@patch("app.llm.providers.anthropic.settings")
def test_status_error_5xx_is_transient_4xx_is_not(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"

    for status_code, expected_transient in [(500, True), (503, True), (400, False), (422, False)]:
        with patch("anthropic.Anthropic") as MockClient:
            fake_response = MagicMock()
            fake_response.status_code = status_code
            MockClient.return_value.messages.create.side_effect = anthropic_sdk.APIStatusError(
                "bad status", response=fake_response, body=None
            )
            with pytest.raises(LLMProviderError) as exc_info:
                provider.complete(_request())
            assert exc_info.value.transient is expected_transient, f"status {status_code}"


@patch("app.llm.providers.anthropic.settings")
def test_unknown_exception_is_not_transient_not_auth(mock_settings):
    mock_settings.anthropic_api_key = "sk-test"
    with patch("anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = RuntimeError("boom")
        with pytest.raises(LLMProviderError) as exc_info:
            provider.complete(_request())

    assert exc_info.value.auth_error is False
    assert exc_info.value.transient is False


def test_missing_api_key_raises_before_calling_sdk():
    with patch("app.llm.providers.anthropic.settings") as mock_settings:
        mock_settings.anthropic_api_key = ""
        with patch("anthropic.Anthropic") as MockClient:
            with pytest.raises(LLMProviderError):
                provider.complete(_request())
            MockClient.assert_not_called()
