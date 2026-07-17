"""
Provider-agnostic data structures for LLM requests and responses.

These types decouple the rest of the application from any specific SDK.
Adding a new provider means implementing a new function in providers/
that accepts LLMRequest and returns LLMResponse — nothing else changes.
"""

from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    role: str    # "user" | "assistant"
    # Plain text for ordinary turns, or a list of Anthropic content blocks
    # (tool_use / tool_result / text) when the turn is part of a tool-calling loop.
    content: str | list[dict]


@dataclass
class LLMRequest:
    model_name: str
    system: str
    messages: list[LLMMessage]
    temperature: float
    max_tokens: int = 1024
    # Anthropic tool schemas (name/description/input_schema) and tool_choice.
    # None means "no tools offered" — behavior is identical to before this field existed.
    tools: list[dict] | None = None
    tool_choice: dict | None = None


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    # "end_turn" | "tool_use" | "max_tokens" | "stop_sequence" — callers that don't
    # care about tool-calling can ignore this; it defaults to a normal-turn value.
    stop_reason: str = "end_turn"
    # Raw content blocks as returned by the provider (text and/or tool_use blocks),
    # needed to replay the assistant's turn verbatim in a tool-calling loop.
    content_blocks: list[dict] = field(default_factory=list)


class LLMProviderError(Exception):
    """
    Raised when the LLM provider returns an error or is unreachable.

    The message is safe to surface to the service layer for logging.
    It must never contain API keys, full prompts, or raw provider stacktraces.
    """

    def __init__(
        self,
        message: str,
        *,
        auth_error: bool = False,
        transient: bool = False,
        provider: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.message = message
        # auth_error: configuration problem (bad/missing API key) — never worth retrying.
        self.auth_error = auth_error
        # transient: retrying with backoff may succeed (rate limit, network blip, 5xx).
        self.transient = transient
        self.provider = provider
