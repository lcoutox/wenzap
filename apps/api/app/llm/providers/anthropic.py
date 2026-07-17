"""
Anthropic provider implementation.

Translates provider-agnostic LLMRequest/LLMResponse to/from the
Anthropic SDK. All SDK-specific exceptions are caught here and
re-raised as LLMProviderError with sanitized messages.

Never logs or exposes the API key or raw prompt content.
"""

import time

import anthropic

from app.config import settings
from app.llm.schemas import LLMProviderError, LLMRequest, LLMResponse


def complete(request: LLMRequest) -> LLMResponse:
    """
    Send a completion request to Anthropic and return a normalized response.

    Raises:
        LLMProviderError: on any SDK error, timeout, or unexpected failure.
    """
    api_key = settings.anthropic_api_key
    if not api_key:
        raise LLMProviderError(
            "Anthropic API key not configured. Set ANTHROPIC_API_KEY in the environment."
        )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    create_kwargs = {
        "model": request.model_name,
        "system": request.system,
        "messages": messages,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }
    if request.tools:
        create_kwargs["tools"] = request.tools
    if request.tool_choice:
        create_kwargs["tool_choice"] = request.tool_choice

    start_ms = time.monotonic()
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(**create_kwargs)
    except anthropic.AuthenticationError:
        raise LLMProviderError(
            "Authentication failed. Check the Anthropic API key configuration.",
            auth_error=True,
            provider="anthropic",
        )
    except anthropic.RateLimitError:
        raise LLMProviderError(
            "Rate limit reached. Please try again in a few moments.",
            transient=True,
            provider="anthropic",
        )
    except anthropic.APIStatusError as exc:
        # Sanitize: include only status code, not the raw body which may contain prompts.
        # 5xx is the provider's own fault and usually transient; 4xx (other than the
        # auth/rate-limit cases already caught above) is a request problem — don't retry.
        raise LLMProviderError(
            f"Anthropic API returned status {exc.status_code}.",
            transient=exc.status_code >= 500,
            provider="anthropic",
        )
    except anthropic.APIConnectionError:
        raise LLMProviderError(
            "Could not connect to the Anthropic API. Check network or retry.",
            transient=True,
            provider="anthropic",
        )
    except Exception:
        # Catch-all: never propagate unknown SDK errors with raw details
        raise LLMProviderError(
            "Unexpected error communicating with the LLM provider.",
            provider="anthropic",
        )

    duration_ms = int((time.monotonic() - start_ms) * 1000)

    # Preserve every block (text and/or tool_use), not just the first one — a
    # tool-calling response can carry a tool_use block with no text at all, or
    # text followed by one or more tool_use blocks.
    content_blocks = [block.model_dump() for block in response.content] if response.content else []
    text_parts = [b["text"] for b in content_blocks if b.get("type") == "text"]

    return LLMResponse(
        content="\n".join(text_parts),
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        duration_ms=duration_ms,
        stop_reason=response.stop_reason or "end_turn",
        content_blocks=content_blocks,
    )
