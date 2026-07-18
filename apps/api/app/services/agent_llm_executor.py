"""
Shared LLM turn executor.

Single place where both the production reply path
(conversation_agent_reply_service.py) and the Playground/test path
(agent_test_service.py) drive one user turn to completion — including
the tool-calling loop and the transient-error retry policy.

Before this module existed, the two call sites had drifted: one had a
retry loop, the other didn't; the executable-model allowlist differed;
credit-increment logic was duplicated near-identically. Centralizing the
turn-execution logic here (not just the tool loop) fixes that drift as a
side effect, and is required anyway — a tool-calling loop implemented
twice, once per call site, would only make the duplication worse.

Callers that don't attach any tools to `LLMRequest.tools` get behavior
identical to a single `llm_client.complete()` call (plus the retry
policy, which already existed at the reply-service call site before this
module and is now just centralized).
"""

import time
from dataclasses import dataclass, field
from typing import Callable

from app.llm import client as llm_client
from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest, LLMResponse
from app.services.agent_guardrails import detect_prompt_injection

# Hard cap on tool-calling round-trips per user turn. Exists purely as a
# safety net against a misbehaving tool/prompt causing an unbounded loop
# that burns AI credits — 5 round-trips is generous for any tool flow we
# support today (a single HTTP tool call rarely needs to be chained more
# than once or twice).
MAX_TOOL_ITERATIONS = 5

_RETRY_BACKOFF_START_MS = 500
_RETRY_BACKOFF_MAX_MS = 5000
_MAX_RETRIES_PER_CALL = 2

# A tool executor receives the tool's `input` dict (as decided by the model)
# and returns the result as plain text to feed back into the conversation.
# Raising is safe — the executor loop catches it and reports the failure to
# the model as a tool error, it never crashes the turn.
ToolExecutor = Callable[[dict], str]


@dataclass
class LLMTurnCallRecord:
    """One LLM round-trip within the loop, with whatever tools it triggered."""

    call_index: int
    stop_reason: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    # Empty list when this round-trip produced no tool_use block (the common
    # case: a plain reply, or the final answer after earlier tool rounds).
    # Each entry: {"tool_name", "tool_use_id", "input", "output", "status"}.
    tool_calls: list[dict] = field(default_factory=list)


@dataclass
class AgentTurnResult:
    content: str
    stop_reason: str
    # Summed across every LLM round-trip in the loop — this is the number
    # callers should use for credit accounting, not any single call's tokens.
    input_tokens: int
    output_tokens: int
    duration_ms: int
    calls: list[LLMTurnCallRecord] = field(default_factory=list)


class ToolIterationLimitError(Exception):
    """The model kept requesting tools past MAX_TOOL_ITERATIONS without a final answer."""


def _complete_with_retries(request: LLMRequest) -> tuple:
    """
    Same retry policy the reply service had before this module existed:
    retry transient errors (rate limit, network, 5xx) with exponential
    backoff, never retry auth errors or non-transient failures.
    """
    last_error: LLMProviderError | None = None
    backoff_ms = _RETRY_BACKOFF_START_MS
    for attempt in range(_MAX_RETRIES_PER_CALL + 1):
        try:
            return llm_client.complete(request)
        except LLMProviderError as exc:
            last_error = exc
            if exc.auth_error or not exc.transient:
                break
            if attempt < _MAX_RETRIES_PER_CALL:
                time.sleep(backoff_ms / 1000.0)
                backoff_ms = min(backoff_ms * 2, _RETRY_BACKOFF_MAX_MS)
    assert last_error is not None
    raise last_error


def _nudge_for_final_reply(
    request: LLMRequest, messages: list[LLMMessage], empty_response: LLMResponse
) -> LLMResponse | None:
    """
    One bounded, tools-disabled follow-up call — used only when a turn's
    final response had no text after the model used at least one tool.
    Replays the model's own (empty) turn verbatim, then asks it directly to
    reply to the customer; `tools=None` rules out yet another tool_use
    response, so this always resolves to plain text (or genuinely gives up).

    Returns None if the nudge call itself fails (network/provider error) —
    a failed *enhancement* must never turn into a failed *turn*; the caller
    falls back to the original (empty) content, same as before this guard
    existed.
    """
    nudge_messages = [
        *messages,
        LLMMessage(role="assistant", content=empty_response.content_blocks),
        LLMMessage(
            role="user",
            content=(
                "Responda ao cliente agora, de forma breve, considerando o que "
                "você acabou de fazer."
            ),
        ),
    ]
    nudge_request = LLMRequest(
        model_name=request.model_name,
        system=request.system,
        messages=nudge_messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        tools=None,
    )
    try:
        return _complete_with_retries(nudge_request)
    except LLMProviderError:
        return None


def run_agent_turn(
    request: LLMRequest,
    *,
    tool_dispatch: dict[str, ToolExecutor] | None = None,
) -> AgentTurnResult:
    """
    Drive one user turn to completion, including any tool-calling round-trips.

    *request* is the fully-built initial LLMRequest — system prompt, the
    starting message(s), model, temperature, and (if the agent has active
    tools) `tools`/`tool_choice` already set by the caller. If `request.tools`
    is empty/None, this behaves exactly like a single retried
    `llm_client.complete()` call.

    *tool_dispatch* maps tool name -> ToolExecutor. Required whenever
    `request.tools` is non-empty; a tool the model calls that isn't in this
    map is reported back to the model as unavailable rather than raising.

    Raises LLMProviderError if the LLM call ultimately fails after retries —
    same exception type callers already handle today, no new except clause
    needed at call sites migrating from a bare `llm_client.complete()` call.

    Raises ToolIterationLimitError if the model keeps calling tools past
    MAX_TOOL_ITERATIONS without producing a final text answer.
    """
    messages = list(request.messages)
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_ms = 0
    calls: list[LLMTurnCallRecord] = []

    for call_index in range(MAX_TOOL_ITERATIONS):
        turn_request = LLMRequest(
            model_name=request.model_name,
            system=request.system,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tools=request.tools,
            tool_choice=request.tool_choice,
        )
        response = _complete_with_retries(turn_request)
        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens
        total_duration_ms += response.duration_ms

        if response.stop_reason != "tool_use":
            final_content = response.content
            final_stop_reason = response.stop_reason

            # Defensive guard (found in production 2026-07-18): a tool result
            # with no explicit "keep talking to the customer" instruction can
            # make the model treat the tool call as the whole turn, ending
            # with zero text. Persisting/delivering that empty string fails
            # downstream (every WhatsApp provider rejects empty text) — so
            # if this turn used at least one tool (`calls` non-empty) and
            # produced no text, nudge once for an actual reply instead of
            # silently returning empty. Never nudges more than once per turn.
            if not final_content.strip() and calls and response.content_blocks:
                nudge = _nudge_for_final_reply(request, messages, response)
                if nudge is not None:
                    total_input_tokens += nudge.input_tokens
                    total_output_tokens += nudge.output_tokens
                    total_duration_ms += nudge.duration_ms
                    if nudge.content.strip():
                        final_content = nudge.content
                        final_stop_reason = nudge.stop_reason

            calls.append(LLMTurnCallRecord(
                call_index=call_index,
                stop_reason=final_stop_reason,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                duration_ms=response.duration_ms,
            ))
            return AgentTurnResult(
                content=final_content,
                stop_reason=final_stop_reason,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                duration_ms=total_duration_ms,
                calls=calls,
            )

        # The model wants to use one or more tools (Anthropic supports
        # requesting several in parallel in a single response). Replay its
        # turn verbatim, execute every tool_use block, and feed results back.
        messages.append(LLMMessage(role="assistant", content=response.content_blocks))

        tool_use_blocks = [b for b in response.content_blocks if b.get("type") == "tool_use"]
        result_blocks = []
        call_record = LLMTurnCallRecord(
            call_index=call_index,
            stop_reason=response.stop_reason,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            duration_ms=response.duration_ms,
        )

        for block in tool_use_blocks:
            tool_name = block.get("name", "")
            tool_use_id = block.get("id", "")
            tool_input = block.get("input") or {}
            executor = (tool_dispatch or {}).get(tool_name)

            if executor is None:
                output_text = f"Tool '{tool_name}' is not available for this agent."
                status = "error"
            else:
                try:
                    output_text = executor(tool_input)
                    status = "success"
                except Exception as exc:  # noqa: BLE001 — a tool failure must never crash the turn
                    output_text = f"Tool execution failed: {exc}"
                    status = "error"

            # Tool output is untrusted data (it can come from a third-party API
            # this agent's owner configured, not from us) — run the same
            # anti-injection check applied to customer messages before letting
            # it flow back into the model's context. Blocked content still
            # counts as an error tool_result so the model reacts accordingly,
            # not as if the tool silently returned nothing.
            if status == "success" and detect_prompt_injection(output_text):
                output_text = (
                    "[Tool result withheld: it matched a prompt-injection pattern "
                    "and was not passed to the model.]"
                )
                status = "blocked"

            call_record.tool_calls.append({
                "tool_name": tool_name,
                "tool_use_id": tool_use_id,
                "input": tool_input,
                "output": output_text,
                "status": status,
            })
            result_blocks.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": output_text,
                "is_error": status != "success",
            })

        calls.append(call_record)
        messages.append(LLMMessage(role="user", content=result_blocks))

    raise ToolIterationLimitError(
        f"Agent turn exceeded {MAX_TOOL_ITERATIONS} tool-calling "
        "iterations without a final response."
    )
