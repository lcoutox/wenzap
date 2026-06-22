"""
Provider-agnostic data structures for LLM requests and responses.

These types decouple the rest of the application from any specific SDK.
Adding a new provider means implementing a new function in providers/
that accepts LLMRequest and returns LLMResponse — nothing else changes.
"""

from dataclasses import dataclass


@dataclass
class LLMMessage:
    role: str    # "user" | "assistant"
    content: str


@dataclass
class LLMRequest:
    model_name: str
    system: str
    messages: list[LLMMessage]
    temperature: float
    max_tokens: int = 1024


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


class LLMProviderError(Exception):
    """
    Raised when the LLM provider returns an error or is unreachable.

    The message is safe to surface to the service layer for logging.
    It must never contain API keys, full prompts, or raw provider stacktraces.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
