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

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_stage import PipelineStage
from app.services.agent_catalog_scope_service import get_allowed_category_ids
from app.services.agent_context_builder import build_rag_context_block, build_system_prompt
from app.services.agent_guardrails import detect_prompt_injection
from app.services.catalog_retrieval_service import (
    CatalogRetrievalItem,
    retrieve_catalog_context,
)
from app.services.context_tier_service import get_tier_config
from app.services.knowledge_retrieval_service import RetrievedChunk, retrieve_context_for_agent

logger = logging.getLogger(__name__)

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

    # Fully assembled system prompt (identity + persona + RAG + catalog + safety rules).
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

    # Catalog retrieval metadata (Catálogo.3).
    catalog_retrieval_attempted: bool = False
    catalog_items_count: int = 0
    catalog_items: list[CatalogRetrievalItem] = field(default_factory=list)
    catalog_error_message: str | None = None

    # All messages included in the history (for debugging / audit).
    history_messages: list[dict[str, Any]] = field(default_factory=list)

    # Pipeline stage extra_prompt injection
    pipeline_extra_prompt_injected: bool = False


def build_conversation_context(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    agent: Agent,
    trigger_message: ConversationMessage,
    history_limit: int | None = None,
    rag_max_chars: int | None = None,
    catalog_limit: int | None = None,
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
    # Resolve per-agent context tier limits, falling back to global config.
    model_settings = db.scalar(
        select(AgentModelSettings).where(AgentModelSettings.agent_id == agent.id)
    )
    tier = getattr(model_settings, "context_window_tier", None) or "standard"
    tier_cfg = get_tier_config(tier)

    limit = history_limit if history_limit is not None else tier_cfg.get(
        "history_limit", app_settings.conversation_history_limit
    )
    effective_rag_max_chars = rag_max_chars if rag_max_chars is not None else tier_cfg.get(
        "rag_max_chars", app_settings.rag_max_context_chars
    )
    effective_catalog_limit = catalog_limit if catalog_limit is not None else tier_cfg.get(
        "catalog_limit", 3
    )

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
    chunks_final = _truncate_chunks_to_limit(chunks_safe, effective_rag_max_chars)

    rag_context: str | None = None
    if chunks_final:
        rag_context = build_rag_context_block([c.content for c in chunks_final])

    # ── Catalog retrieval (Catálogo.3 / Catálogo.5 / Agent Tools.2) ─────────
    if agent.catalog_enabled:
        allowed_category_ids = get_allowed_category_ids(
            db, agent_id=agent.id, workspace_id=workspace_id
        )
        catalog_result = retrieve_catalog_context(
            db,
            workspace_id=workspace_id,
            query=trigger_message.content,
            limit=effective_catalog_limit,
            allowed_category_ids=allowed_category_ids,
        )
    else:
        from app.services.catalog_retrieval_service import CatalogRetrievalResult  # noqa: PLC0415
        catalog_result = CatalogRetrievalResult(retrieval_attempted=False)

    # ── Build system prompt (reuses Playground builder unchanged) ─────────────
    ps_response_style = getattr(prompt_settings, "response_style", None)
    ps_language_mode = getattr(prompt_settings, "language_mode", None)
    ps_knowledge_only = getattr(prompt_settings, "knowledge_only", False)
    ps_show_sources = getattr(prompt_settings, "show_sources", False)

    system = build_system_prompt(
        agent_name=agent.name,
        agent_description=agent.description,
        system_prompt=prompt_settings.system_prompt or "",
        persona=prompt_settings.persona,
        response_style=ps_response_style,
        language_mode=ps_language_mode,
        knowledge_only=ps_knowledge_only,
        show_sources=ps_show_sources,
        rag_context=rag_context,
        catalog_context=catalog_result.context_block,
        channel_hint=conversation.channel_type,
    )

    # ── Pipeline stage extra_prompt injection ─────────────────────────────────
    pipeline_extra_prompt_injected = False
    active_entry = db.scalar(
        select(PipelineEntry).where(
            PipelineEntry.conversation_id == conversation.id,
            PipelineEntry.status == "active",
        )
    )
    if active_entry is not None and active_entry.stage_id is not None:
        active_stage = db.scalar(
            select(PipelineStage).where(PipelineStage.id == active_entry.stage_id)
        )
        if active_stage is not None and active_stage.extra_prompt:
            extra = active_stage.extra_prompt.strip()
            system = system + f"\n\n## INSTRUÇÕES DESTA ETAPA\n\n{extra}"
            pipeline_extra_prompt_injected = True

    if app_settings.ai_prompt_debug:
        _log_prompt_debug(
            agent_id=agent.id,
            conversation_id=conversation.id,
            channel_type=conversation.channel_type,
            has_custom_instructions=bool(prompt_settings.system_prompt),
            has_tone=bool(prompt_settings.persona),
            response_style=ps_response_style,
            has_knowledge_context=bool(rag_context),
            has_catalog_context=bool(catalog_result.context_block),
            system_prompt=system,
        )

    return ConversationContext(
        system_prompt=system,
        conversation_history=history_block,
        reply_instruction=_REPLY_INSTRUCTION,
        rag_used=len(chunks_final) > 0,
        retrieved_chunks_count=len(chunks_final),
        retrieval_duration_ms=retrieval_result.retrieval_duration_ms,
        retrieval_error_message=retrieval_result.error_message,
        catalog_retrieval_attempted=catalog_result.retrieval_attempted,
        catalog_items_count=len(catalog_result.items),
        catalog_items=catalog_result.items,
        catalog_error_message=catalog_result.error_message,
        history_messages=[
            {
                "direction": m.direction,
                "sender_type": m.sender_type,
                "content": m.content,
            }
            for m in messages
        ],
        pipeline_extra_prompt_injected=pipeline_extra_prompt_injected,
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


# ── Debug helpers ─────────────────────────────────────────────────────────────

def _log_prompt_debug(
    *,
    agent_id: uuid.UUID,
    conversation_id: uuid.UUID,
    channel_type: str | None,
    has_custom_instructions: bool,
    has_tone: bool,
    response_style: str | None,
    has_knowledge_context: bool,
    has_catalog_context: bool,
    system_prompt: str,
) -> None:
    """Log structured prompt metadata when AI_PROMPT_DEBUG=true.

    Never logs sensitive customer data. In dev (non-production), also logs the
    first 2000 chars of the assembled system prompt for inspection.
    """
    from app.config import settings as _settings  # noqa: PLC0415 — avoid module-level import

    sections: list[str] = ["identity"]
    if has_custom_instructions:
        sections.append("operator_instructions")
    if has_tone:
        sections.append("persona")
    if response_style:
        sections.append(f"response_style:{response_style}")
    if has_knowledge_context:
        sections.append("rag")
    if has_catalog_context:
        sections.append("catalog")
    sections.append("safety_rules")

    logger.info(
        "AI_PROMPT_DEBUG agent_id=%s conversation_id=%s channel_type=%s "
        "sections=%s system_prompt_length=%d "
        "has_custom_instructions=%s has_tone=%s response_style=%s "
        "has_knowledge_context=%s has_catalog_context=%s",
        agent_id,
        conversation_id,
        channel_type,
        ",".join(sections),
        len(system_prompt),
        has_custom_instructions,
        has_tone,
        response_style,
        has_knowledge_context,
        has_catalog_context,
    )

    # Preview only in dev — never in production to avoid leaking operator config.
    is_dev = not _settings.auth_cookie_secure  # auth_cookie_secure=True only in prod
    if is_dev:
        preview = system_prompt[:2000]
        logger.info("AI_PROMPT_DEBUG system_prompt_preview:\n%s", preview)


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
    stub.response_style = None   # defaults to "balanced" in builder
    stub.language_mode = None    # defaults to "auto" in builder
    stub.knowledge_only = False
    stub.show_sources = False
    return stub
