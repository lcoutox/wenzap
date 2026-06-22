"""
LLM client — public entry point for the rest of the application.

Phase 3 dispatches all requests to the Anthropic provider.
Future phases can add a provider registry / routing by model_name prefix
without changing any caller outside this module.
"""

from app.llm.providers import anthropic as anthropic_provider
from app.llm.schemas import LLMRequest, LLMResponse


def complete(request: LLMRequest) -> LLMResponse:
    """
    Execute an LLM completion request.

    Phase 3: always routes to Anthropic.
    Future: switch on request.model_name or an explicit provider field.
    """
    return anthropic_provider.complete(request)
