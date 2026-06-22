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

    start_ms = time.monotonic()
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=request.model_name,
            system=request.system,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except anthropic.AuthenticationError:
        raise LLMProviderError("Authentication failed. Check the Anthropic API key configuration.")
    except anthropic.RateLimitError:
        raise LLMProviderError("Rate limit reached. Please try again in a few moments.")
    except anthropic.APIStatusError as exc:
        # Sanitize: include only status code, not the raw body which may contain prompts
        raise LLMProviderError(f"Anthropic API returned status {exc.status_code}.")
    except anthropic.APIConnectionError:
        raise LLMProviderError("Could not connect to the Anthropic API. Check network or retry.")
    except Exception:
        # Catch-all: never propagate unknown SDK errors with raw details
        raise LLMProviderError("Unexpected error communicating with the LLM provider.")

    duration_ms = int((time.monotonic() - start_ms) * 1000)

    content = response.content[0].text if response.content else ""
    return LLMResponse(
        content=content,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        duration_ms=duration_ms,
    )
