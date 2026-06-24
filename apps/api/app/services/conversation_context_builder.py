"""
Conversation Context Builder — Phase 5.3.2.

Builds the full context (system prompt + conversation history + RAG) needed
for the ConversationAgentReplyService to call the LLM when a customer message
arrives in the Inbox.

This module is intentionally free of LLM calls, credit checks, and DB writes.
It is a pure read-and-assemble step so it can be tested in isolation.

Separation from agent_context_builder:
  agent_context_builder builds the system prompt for a single standalone message
  (Playground). This builder adds conversation history so the agent is aware of
  the full exchange, not just the current message. The underlying helpers
  (build_system_prompt, build_rag_context_block) are reused unchanged.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.agent import Agent
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.services.agent_context_builder import build_rag_context_block, build_system_prompt
from app.services.agent_guardrails import detect_prompt_injection
from app.services.knowledge_retrieval_service import RetrievedChunk, retrieve_context_for_agent

# Maps (direction, sender_type) to the label shown in the conversation history block.
# Kept explicit so new roles can be added without guessing.
SENDER_LABELS: dict[tuple[str, str], str] = {
    ("inbound",  "customer"): "Cliente",
    ("outbound", "human"):    "Humano",
    ("outbound", "agent"):    "Agente",
    ("internal", "system"):   "Sistema",
    ("internal", "human"):    "Humano (nota)",
}

_FALLBACK_LABEL = "Mensagem"
_HISTORY_HEADER = "Recent conversation history:"
_REPLY_INSTRUCTION = (
    "Responda à última mensagem do cliente de forma útil, clara e consistente "
    "com as instruções do agente."
)


@dataclass
class ConversationContext:
    """
    Assembled context for a single automatic agent reply.

    Consumed by ConversationAgentReplyService (5.3.3) — only fields
    needed to call the LLM and log the run are exposed here.
    """

    # Fully assembled system prompt (identity + persona + RAG + safety rules).
    system_prompt: str

    # Formatted conversation history block (header + labelled lines).
    conversation_history: str

    # Final instruction appended after the history.
    reply_instruction: str

    # RAG metadata — populated regardless of whether RAG succeeded.
    rag_used: bool = False
    retrieved_chunks_count: int = 0
    retrieval_duration_ms: int | None = None
    retrieval_error_message: str | None = None

    # All messages included in the history (for debugging / audit).
    history_messages: list[dict[str, Any]] = field(default_factory=list)


def build_conversation_context(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    agent: Agent,
    trigger_message: ConversationMessage,
    history_limit: int | None = None,
) -> ConversationContext:
    """
    Build the full context for an automatic agent reply.

    Parameters
    ----------
    db              : Active DB session (read-only in this function).
    workspace_id    : Must match conversation.workspace_id — enforced internally.
    conversation    : The conversation being replied to.
    agent           : The agent assigned to this conversation.
    trigger_message : The customer message that triggered the reply.
    history_limit   : Override for the number of recent messages to include.
                      Defaults to settings.conversation_history_limit (20).

    Returns
    -------
    ConversationContext with all fields populated.
    """
    limit = history_limit if history_limit is not None else app_settings.conversation_history_limit

    # ── Load agent prompt settings ────────────────────────────────────────────
    prompt_settings = _load_prompt_settings(db, agent)

    # ── Fetch conversation history ────────────────────────────────────────────
    messages = _fetch_history(db, workspace_id, conversation.id, trigger_message, limit)
    history_block = _format_history(messages)

    # ── RAG retrieval ─────────────────────────────────────────────────────────
    retrieval_result = retrieve_context_for_agent(
        db,
        workspace_id=workspace_id,
        agent_id=agent.id,
        query=trigger_message.content,
    )

    chunks_safe = _filter_chunks_injection(retrieval_result.chunks)
    chunks_final = _truncate_chunks_to_limit(chunks_safe, app_settings.rag_max_context_chars)

    rag_context: str | None = None
    if chunks_final:
        rag_context = build_rag_context_block([c.content for c in chunks_final])

    # ── Build system prompt (reuses Playground builder unchanged) ─────────────
    system = build_system_prompt(
        agent_name=agent.name,
        agent_description=agent.description,
        system_prompt=prompt_settings.system_prompt or "",
        persona=prompt_settings.persona,
        rag_context=rag_context,
    )

    return ConversationContext(
        system_prompt=system,
        conversation_history=history_block,
        reply_instruction=_REPLY_INSTRUCTION,
        rag_used=len(chunks_final) > 0,
        retrieved_chunks_count=len(chunks_final),
        retrieval_duration_ms=retrieval_result.retrieval_duration_ms,
        retrieval_error_message=retrieval_result.error_message,
        history_messages=[
            {
                "direction": m.direction,
                "sender_type": m.sender_type,
                "content": m.content,
            }
            for m in messages
        ],
    )


# ── History helpers ───────────────────────────────────────────────────────────

def _fetch_history(
    db: Session,
    workspace_id: uuid.UUID,
    conversation_id: uuid.UUID,
    trigger_message: ConversationMessage,
    limit: int,
) -> list[ConversationMessage]:
    """
    Return the last *limit* messages in the conversation, including the trigger.

    The trigger message is always the last entry. Messages from other workspaces
    or conversations are excluded by the WHERE clause.
    """
    # Fetch limit messages ordered by created_at DESC (most recent first).
    rows = db.scalars(
        select(ConversationMessage)
        .where(
            ConversationMessage.workspace_id == workspace_id,
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.content != "",
        )
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    ).all()

    # Reverse to get chronological order.
    messages = list(reversed(rows))

    # Deduplicate: if the trigger is already in the fetched window, use as-is.
    # If the window didn't include it (e.g. created after the query snapshot),
    # append it. Comparison by id.
    ids_in_window = {m.id for m in messages}
    if trigger_message.id not in ids_in_window:
        messages.append(trigger_message)

    return messages


def _format_history(messages: list[ConversationMessage]) -> str:
    """
    Format a list of messages into the history block sent to the LLM.

    Returns an empty string when there are no messages.
    """
    if not messages:
        return ""

    lines: list[str] = [_HISTORY_HEADER]
    for msg in messages:
        label = SENDER_LABELS.get((msg.direction, msg.sender_type), _FALLBACK_LABEL)
        content = msg.content.strip()
        if content:
            lines.append(f"{label}: {content}")

    return "\n".join(lines)


# ── RAG helpers (mirrors agent_test_service, not shared to avoid coupling) ────

def _filter_chunks_injection(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Exclude chunks whose content contains prompt-injection patterns."""
    return [c for c in chunks if not detect_prompt_injection(c.content)]


def _truncate_chunks_to_limit(
    chunks: list[RetrievedChunk],
    max_chars: int,
) -> list[RetrievedChunk]:
    """Drop lowest-ranked chunks that would exceed max_chars total."""
    result: list[RetrievedChunk] = []
    total = 0
    for chunk in chunks:
        chunk_len = len(chunk.content)
        if chunk_len > max_chars:
            continue
        if total + chunk_len > max_chars:
            break
        result.append(chunk)
        total += chunk_len
    return result


# ── Prompt settings loader ────────────────────────────────────────────────────

def _load_prompt_settings(db: Session, agent: Agent) -> AgentPromptSettings:
    """
    Load AgentPromptSettings for the agent, falling back to agent columns
    for agents created before Phase 2.4 (same pattern as agent_test_service).

    Does NOT raise for missing system_prompt — the Reply Service is responsible
    for deciding whether to proceed without a prompt (skipped run).
    """
    ps = db.scalar(
        select(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent.id)
    )
    if ps is not None:
        return ps

    # Fallback: synthesise a stub from the agent's own columns.
    stub = AgentPromptSettings.__new__(AgentPromptSettings)
    stub.system_prompt = agent.system_prompt or ""
    stub.persona = agent.persona
    return stub
