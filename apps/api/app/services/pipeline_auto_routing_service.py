"""
Pipeline entry_condition auto-routing — Pipeline.2 Fase 2.

After a customer message is processed, checks whether the conversation's
active pipeline entry should move to a different stage based on each
candidate stage's entry_condition. This does NOT require tool-calling: it's
a small, separate classification call (JSON-structured prompt), the same
trick FluxVolt itself uses ("the system evaluates the condition").

Gated behind the pipeline_automations plan feature — never runs for
workspaces that don't have it, so there's no surprise LLM cost on Free/Growth.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import client as llm_client
from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_stage import PipelineStage
from app.services import pipeline_service
from app.services.plan_feature_service import workspace_allows_feature

logger = logging.getLogger(__name__)

# Cheap/fast model used for the classification call — independent of whatever
# model the workspace configured for the agent's actual replies.
_CLASSIFIER_MODEL = "claude-haiku-4-5"
_HISTORY_LIMIT = 10

_SYSTEM_PROMPT = """\
Você avalia se uma conversa de atendimento deve mudar de etapa dentro de um \
pipeline (CRM). Cada etapa candidata tem uma condição de entrada em \
linguagem natural, escrita por um operador humano.

Responda APENAS com um JSON no formato exato:
{"should_move": true|false, "target_stage_id": "<uuid ou null>"}

Mova a conversa somente quando o conteúdo das mensagens deixar claro que a \
condição de alguma etapa foi satisfeita. Na dúvida, não mova \
(should_move: false, target_stage_id: null). Nunca invente um stage_id que \
não esteja na lista de etapas candidatas."""


def maybe_route_conversation(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
) -> None:
    """
    Best-effort: never raises. Call after a reply has already been generated
    and committed, so a classification failure never blocks the actual reply.
    """
    try:
        _maybe_route_conversation(db, workspace_id, conversation)
    except Exception:
        logger.exception(
            "pipeline_auto_routing unexpected error conversation_id=%s", conversation.id
        )


def _maybe_route_conversation(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
) -> None:
    if not workspace_allows_feature(db, workspace_id, "pipeline_automations"):
        return

    entry = db.scalar(
        select(PipelineEntry).where(
            PipelineEntry.conversation_id == conversation.id,
            PipelineEntry.status == "active",
        )
    )
    if entry is None or entry.pipeline_id is None:
        return

    candidates = list(
        db.scalars(
            select(PipelineStage).where(
                PipelineStage.pipeline_id == entry.pipeline_id,
                PipelineStage.id != entry.stage_id,
                PipelineStage.entry_condition.is_not(None),
            )
        ).all()
    )
    candidates = [c for c in candidates if c.entry_condition and c.entry_condition.strip()]
    if not candidates:
        return

    messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(_HISTORY_LIMIT)
    ).all()
    history_lines = [
        f"{'Cliente' if m.direction == 'inbound' else 'Agente'}: {m.content.strip()}"
        for m in reversed(list(messages))
        if m.content and m.content.strip()
    ]
    if not history_lines:
        return

    stage_list = "\n".join(
        f'- id="{c.id}" nome="{c.name}" condição="{c.entry_condition.strip()}"'
        for c in candidates
    )
    user_prompt = (
        f"Etapas candidatas:\n{stage_list}\n\n"
        f"Últimas mensagens da conversa:\n" + "\n".join(history_lines)
    )

    request = LLMRequest(
        model_name=_CLASSIFIER_MODEL,
        system=_SYSTEM_PROMPT,
        messages=[LLMMessage(role="user", content=user_prompt)],
        temperature=0.0,
        max_tokens=200,
    )

    try:
        response = llm_client.complete(request)
    except LLMProviderError:
        logger.warning(
            "pipeline_auto_routing classifier call failed conversation_id=%s", conversation.id
        )
        return

    decision = _parse_decision(response.content, {str(c.id) for c in candidates})
    if decision is None:
        return

    target_stage = next((c for c in candidates if str(c.id) == decision), None)
    if target_stage is None:
        return

    previous_stage_id = entry.stage_id
    now = datetime.now(timezone.utc)
    entry.stage_id = target_stage.id
    entry.entered_stage_at = now
    entry.updated_at = now

    pipeline_service.apply_stage_entry_effects(
        db, workspace_id, entry, target_stage, previous_stage_id, "entry_condition"
    )
    db.commit()

    logger.info(
        "pipeline_auto_routing moved conversation_id=%s entry_id=%s to stage_id=%s",
        conversation.id, entry.id, target_stage.id,
    )


def _parse_decision(raw_content: str, valid_stage_ids: set[str]) -> str | None:
    """Extract target_stage_id from the classifier's JSON response, or None."""
    text = raw_content.strip()
    # Defensive: models sometimes wrap JSON in a code fence despite instructions.
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("pipeline_auto_routing could not parse classifier response: %r", text[:200])
        return None

    if not isinstance(parsed, dict) or not parsed.get("should_move"):
        return None
    target = parsed.get("target_stage_id")
    if not isinstance(target, str) or target not in valid_stage_ids:
        return None
    return target
