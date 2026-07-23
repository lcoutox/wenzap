"""
Conversation Agent Reply Service — Phase 5.3.3.

Generates an automatic agent reply for a customer message received in the Inbox.

This service is called by the auto-trigger (Phase 5.3.4) after a customer
message is created. It is intentionally NOT connected to any endpoint or
ConversationMessageService yet — it runs in isolation in this phase.

Design decisions:
  - Returns ConversationAgentRun | None.
    None is returned when eligibility fails BEFORE we have enough context to
    create a run (no agent_id, trigger not from customer, etc.).
    A ConversationAgentRun is returned for every case where the agent is known.
  - Credits consumed ONLY on LLM success, atomically with the run insert.
  - The response ConversationMessage, credit increment, and run INSERT are all
    flushed in the same transaction, committed together for consistency.
  - Failures/skips/blocked produce a run with status != "success" and no
    response message, no credit consumption.
  - RAG retrieval failure degrades gracefully: LLM is still called without
    RAG context. The run records rag_used=False and the retrieval error message.
"""

import base64
import logging
import uuid
from datetime import datetime, timezone

import sentry_sdk
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.llm.schemas import LLMMessage, LLMProviderError, LLMRequest
from app.models.agent import Agent
from app.models.agent_model_settings import AgentModelSettings
from app.models.agent_prompt_settings import AgentPromptSettings
from app.models.agent_tool_call import AgentToolCall
from app.models.ai_model import AiModel
from app.models.ai_model_provider import AiModelProvider
from app.models.conversation import Conversation
from app.models.conversation_agent_run import ConversationAgentRun
from app.models.conversation_message import ConversationMessage
from app.models.plan import Plan
from app.models.usage_counter import UsageCounter
from app.models.workspace_subscription import WorkspaceSubscription
from app.services.agent_guardrails import detect_prompt_injection
from app.services.agent_llm_executor import run_agent_turn
from app.services.agent_tool_service import (
    build_tool_dispatch,
    build_tool_schema,
    get_enabled_tools_for_agent,
)
from app.services.context_tier_service import calculate_credits
from app.services.conversation_context_builder import build_conversation_context
from app.services.plan_feature_service import plan_allows_feature

logger = logging.getLogger(__name__)

# Re-use the same executable model set as the Playground.
# Inbox replies use the same LLM infrastructure.
ANTHROPIC_EXECUTABLE_MODELS: set[str] = {
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
}

# ── Error codes ───────────────────────────────────────────────────────────────

EC_NOT_CUSTOMER_INBOUND = "not_customer_inbound"
EC_AI_DISABLED = "ai_disabled"
EC_NO_AGENT = "no_agent"
EC_STATUS_NOT_ALLOWED = "status_not_allowed"
EC_HUMAN_ASSIGNED = "human_assigned"
EC_AGENT_NOT_FOUND = "agent_not_found"
EC_AGENT_INACTIVE = "agent_inactive"
EC_NO_MODEL = "no_model"
EC_NO_CREDITS = "no_credits"
EC_PROMPT_INJECTION = "prompt_injection"
EC_LLM_ERROR = "llm_error"
EC_CONTEXT_ERROR = "context_error"
EC_UNKNOWN_ERROR = "unknown_error"

_ALLOWED_CONV_STATUSES = {"open", "pending"}


def generate_conversation_agent_reply(
    db: Session,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    trigger_message: ConversationMessage,
) -> ConversationAgentRun | None:
    """
    Attempt to generate an automatic agent reply for *trigger_message*.

    Returns
    -------
    ConversationAgentRun
        Always returned when the agent is known (active or inactive, model
        found or not, LLM succeeded or failed).
    None
        Returned when eligibility fails before we can identify a valid agent:
        - trigger message is not inbound/customer
        - conversation.ai_enabled is False
        - conversation.agent_id is None
        - conversation.status is resolved/archived
        - conversation.assigned_user_id is set (human has taken over)
        - agent record not found / FK gone (can't reference in run)
    """
    # ── 1. Trigger message must be inbound/customer ───────────────────────────
    if trigger_message.direction != "inbound" or trigger_message.sender_type != "customer":
        return None  # not_customer_inbound — no run, no noise

    # ── 2. Conversation eligibility ───────────────────────────────────────────
    if not conversation.ai_enabled:
        logger.info("agent_reply_skip reason=ai_disabled conversation_id=%s", conversation.id)
        return None
    if conversation.agent_id is None:
        logger.info("agent_reply_skip reason=no_agent conversation_id=%s", conversation.id)
        return None
    if conversation.status not in _ALLOWED_CONV_STATUSES:
        logger.info(
            "agent_reply_skip reason=status_%s conversation_id=%s",
            conversation.status,
            conversation.id,
        )
        return None
    if conversation.assigned_user_id is not None:
        logger.info(
            "agent_reply_skip reason=human_assigned conversation_id=%s assigned_user_id=%s",
            conversation.id,
            conversation.assigned_user_id,
        )
        return None

    # ── 3. Load agent (workspace-scoped) ─────────────────────────────────────
    agent = db.scalar(
        select(Agent).where(
            Agent.id == conversation.agent_id,
            Agent.workspace_id == workspace_id,
        )
    )
    if agent is None:
        logger.info(
            "agent_reply_skip reason=agent_not_found conversation_id=%s agent_id=%s",
            conversation.id,
            conversation.agent_id,
        )
        return None

    if agent.status != "active":
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=None,
            status="skipped",
            error_code=EC_AGENT_INACTIVE,
        )

    # ── 4. Load model settings ────────────────────────────────────────────────
    model_settings = db.scalar(
        select(AgentModelSettings).where(AgentModelSettings.agent_id == agent.id)
    )
    if model_settings is None:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=None,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message="Agent has no model configured.",
        )

    model = db.scalar(select(AiModel).where(AiModel.id == model_settings.ai_model_id))
    if model is None or not model.is_active:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message="Configured model not found or inactive.",
        )

    provider = db.scalar(select(AiModelProvider).where(AiModelProvider.id == model.provider_id))
    if provider is None or not provider.is_active:
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message="Model provider not found or inactive.",
        )

    # Only Anthropic/Nexbrain models are executable in this phase.
    if (
        provider.code.lower() not in ("anthropic", "nexbrain")
        or model.model_name not in ANTHROPIC_EXECUTABLE_MODELS
    ):
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_MODEL,
            error_message=(f"Model '{model.model_name}' is not supported for automatic replies."),
        )

    # ── 5. Credit check ───────────────────────────────────────────────────────
    tier = getattr(model_settings, "context_window_tier", None) or "standard"
    credits_needed = calculate_credits(model.credits_per_message, tier)
    plan_code = _get_workspace_plan_code(db, workspace_id)
    counter = _get_usage_counter(db, workspace_id)
    if counter is None or not _has_credits(db, counter, credits_needed, plan_code):
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_NO_CREDITS,
            error_message="Insufficient AI credits.",
        )

    # ── 6. Prompt injection guard ─────────────────────────────────────────────
    if detect_prompt_injection(trigger_message.content):
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="blocked",
            error_code=EC_PROMPT_INJECTION,
            error_message="Trigger message blocked by guardrails.",
        )

    # ── 7. Build conversation context ─────────────────────────────────────────
    # http_request tools only actually get attached if the workspace's plan
    # still allows http_tools — a downgraded workspace just loses that tool on
    # its next reply rather than erroring the whole turn. request_human has no
    # plan gate (available on every plan), so it's never filtered out here.
    # Reuses plan_code already resolved for the credit check above instead of
    # a second lookup.
    tool_dispatch = None
    tools_schema = None
    enabled_tools = get_enabled_tools_for_agent(db, workspace_id, agent.id)
    if enabled_tools:
        http_tools_allowed = plan_allows_feature(db, plan_code, "http_tools")
        usable_tools = [
            t for t in enabled_tools if t.tool_type != "http_request" or http_tools_allowed
        ]
        if usable_tools:
            tools_schema = [build_tool_schema(t) for t in usable_tools]
            tool_dispatch = build_tool_dispatch(
                usable_tools, db=db, workspace_id=workspace_id, conversation=conversation
            )

    try:
        ctx = build_conversation_context(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            agent=agent,
            trigger_message=trigger_message,
            has_tools=bool(tools_schema),
        )
    except Exception as exc:  # noqa: BLE001
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_CONTEXT_ERROR,
            error_message=f"Context build error: {str(exc)[:400]}",
        )

    # ── 8. Call LLM ───────────────────────────────────────────────────────────
    # Build the user turn: history block + reply instruction, so the model
    # sees the full conversation before the latest customer message.
    user_turn = (
        f"{ctx.conversation_history}\n\n{ctx.reply_instruction}"
        if ctx.conversation_history
        else ctx.reply_instruction
    )

    # conversation-image-upload-prd.md: if the trigger message carries an
    # image, attach it as a vision content block — but only when the
    # agent's configured model actually supports vision. Otherwise (no
    # vision support, or the stored image couldn't be read back), the model
    # still gets told an image arrived instead of silently seeing nothing,
    # so it can react with context (ask to describe it, offer a human) —
    # see "Decisão pendente #3" in the PRD for the alternative (Chatvolt's
    # silent-ignore behavior) if this default needs revisiting.
    message_content: str | list[dict] = user_turn
    # getattr, not direct attribute access: some callers/tests pass lightweight
    # stand-ins for trigger_message that don't set every ConversationMessage
    # column — a real ORM row always has both, so this changes nothing in
    # production.
    trigger_content_type = getattr(trigger_message, "content_type", None)
    trigger_media_url = getattr(trigger_message, "media_url", None)
    if trigger_content_type == "image" and trigger_media_url:
        image_block = _build_image_content_block(trigger_message) if model.supports_vision else None
        if image_block is not None:
            message_content = [image_block, {"type": "text", "text": user_turn}]
        else:
            reason = (
                "o modelo configurado para este agente não tem suporte a visão"
                if not model.supports_vision
                else "não foi possível carregar a imagem enviada"
            )
            message_content = (
                f"{user_turn}\n\n[O cliente enviou uma imagem, mas {reason} — "
                "a imagem não pôde ser interpretada.]"
            )

    request = LLMRequest(
        model_name=model.model_name,
        system=ctx.system_prompt,
        messages=[LLMMessage(role="user", content=message_content)],
        temperature=float(model_settings.temperature),
        tools=tools_schema,
    )

    # ── Call LLM via the shared executor (handles retries + tool-calling loop) ─
    # Ambient Sentry context for this turn — any event captured inside (e.g.
    # a tool call failing, see agent_llm_executor.py) inherits these tags
    # without needing workspace/agent/conversation threaded through the
    # executor itself.
    try:
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("workspace_id", str(workspace_id))
            scope.set_tag("agent_id", str(agent.id))
            scope.set_context(
                "conversation",
                {
                    "workspace_id": str(workspace_id),
                    "agent_id": str(agent.id),
                    "conversation_id": str(conversation.id),
                    "trigger_message_id": str(trigger_message.id),
                },
            )
            llm_response = run_agent_turn(request, tool_dispatch=tool_dispatch)
    except LLMProviderError as exc:
        # Notify admin of the error
        from app.services.agent_alert_service import notify_agent_error  # noqa: PLC0415

        notify_agent_error(
            db,
            workspace_id=workspace_id,
            agent_id=agent.id,
            conversation_id=conversation.id,
            error_code=EC_LLM_ERROR,
            error_message=str(exc.message)[:500],
            error_details={
                "auth_error": exc.auth_error,
                "transient": exc.transient,
                "provider": exc.provider if hasattr(exc, "provider") else "unknown",
            },
        )
        return _save_run(
            db,
            workspace_id=workspace_id,
            conversation=conversation,
            trigger_message=trigger_message,
            agent=agent,
            model=model,
            status="failed",
            error_code=EC_LLM_ERROR,
            error_message=str(exc.message)[:500],
            rag_used=ctx.rag_used,
            retrieved_chunks_count=ctx.retrieved_chunks_count,
            retrieval_duration_ms=ctx.retrieval_duration_ms,
        )

    # ── 9. Persist response message ───────────────────────────────────────────
    now = datetime.now(timezone.utc)

    # Last-resort safety net: run_agent_turn's own nudge (agent_llm_executor.py)
    # already handles the common case of an empty final reply after a tool
    # call, so this should essentially never fire. But every WhatsApp
    # provider rejects an empty text send, so we must not persist/deliver ""
    # under any circumstance — a generic filler beats a failed delivery.
    reply_content = llm_response.content
    if not reply_content.strip():
        logger.warning(
            "agent_reply_empty_content_after_nudge conversation_id=%s "
            "trigger_message_id=%s agent_id=%s",
            conversation.id,
            trigger_message.id,
            agent.id,
        )
        reply_content = "Certo!"

    # Build metadata_json for audit (catalog retrieval info, safe to store).
    response_metadata: dict = {}
    if ctx.catalog_retrieval_attempted:
        methods = {i.retrieval_method for i in ctx.catalog_items}
        method = (
            "full_catalog"
            if "full_catalog" in methods
            else "hybrid"
            if "hybrid" in methods
            else "lexical_fallback"
            if methods
            else "none"
        )
        response_metadata["catalog_retrieval"] = {
            "query": trigger_message.content[:500],
            "retrieval_method": method,
            "embedding_used": method == "hybrid",
            "items_considered": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "score": item.score,
                    "semantic_score": item.semantic_score,
                    "lexical_score": item.lexical_score,
                    "retrieval_method": item.retrieval_method,
                }
                for item in ctx.catalog_items
            ],
        }

    response_msg = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_type="agent",
        agent_id=agent.id,
        content=reply_content,
        content_type="text",
        metadata_json=response_metadata or None,
    )
    db.add(response_msg)
    db.flush()  # Assign id and created_at.

    # Update conversation timestamps.
    conversation.last_message_at = response_msg.created_at or now
    conversation.updated_at = now

    # ── 10. Consume credits (atomic) ──────────────────────────────────────────
    _increment_credits(db, workspace_id, credits_needed)

    # ── 11. Persist success run ───────────────────────────────────────────────
    # The turn itself completed fine (status stays "success"), but a tool
    # call inside it may still have failed (e.g. Cal.com rejecting a
    # booking) — had_tool_error tracks that separately so the Auditoria
    # screen and the Inbox indicator can surface it.
    had_tool_error = any(
        tc.get("status") == "error" for call in llm_response.calls for tc in call.tool_calls
    )
    run = ConversationAgentRun(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        trigger_message_id=trigger_message.id,
        response_message_id=response_msg.id,
        agent_id=agent.id,
        ai_model_id=model.id,
        status="success",
        had_tool_error=had_tool_error,
        credits_used=credits_needed,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.output_tokens,
        duration_ms=llm_response.duration_ms,
        rag_used=ctx.rag_used,
        retrieved_chunks_count=ctx.retrieved_chunks_count,
        retrieval_duration_ms=ctx.retrieval_duration_ms,
        # Surface retrieval errors in error_message even on success so they
        # are visible in logs without marking the run as failed.
        error_message=ctx.retrieval_error_message,
    )
    db.add(run)
    db.flush()  # assign run.id before creating tool-call audit rows below

    # Only audit when tools were actually attached this turn — the common
    # case (no tools enabled) would otherwise insert a redundant empty row
    # on every single reply.
    if tools_schema:
        for call in llm_response.calls:
            db.add(
                AgentToolCall(
                    workspace_id=workspace_id,
                    conversation_agent_run_id=run.id,
                    call_index=call.call_index,
                    stop_reason=call.stop_reason,
                    input_tokens=call.input_tokens,
                    output_tokens=call.output_tokens,
                    duration_ms=call.duration_ms,
                    tool_calls=call.tool_calls,
                )
            )

    db.commit()
    db.refresh(run)

    logger.info(
        "agent_reply_success conversation_id=%s run_id=%s response_message_id=%s",
        conversation.id,
        run.id,
        response_msg.id,
    )

    # Pipeline.2 Fase 2 — best-effort auto-routing by entry_condition. Runs
    # after the reply is already committed so a classifier failure never
    # blocks the actual customer-facing reply.
    from app.services.pipeline_auto_routing_service import maybe_route_conversation  # noqa: PLC0415

    maybe_route_conversation(db, workspace_id, conversation)

    # Deliver agent reply to WhatsApp when the conversation came from that channel.
    if conversation.channel_type == "whatsapp":
        try:
            from app.services.messaging import deliver_outbound_message  # noqa: PLC0415

            deliver_outbound_message(db, response_msg, conversation)
        except Exception:
            logger.exception(
                "whatsapp_outbound agent delivery failed conversation=%s message=%s",
                conversation.id,
                response_msg.id,
            )

        # After text delivery: attempt catalog image delivery if eligible.
        text_delivered = (response_msg.metadata_json or {}).get("delivery", {}).get(
            "status"
        ) == "sent"
        if text_delivered and agent.catalog_enabled and ctx.catalog_retrieval_attempted:
            try:
                from app.services.catalog_media_delivery_service import (  # noqa: PLC0415
                    decide_catalog_media_delivery,
                    deliver_catalog_media_image,
                )
                from app.services.storage.factory import get_storage_provider  # noqa: PLC0415

                decision = decide_catalog_media_delivery(
                    db=db,
                    workspace_id=workspace_id,
                    conversation=conversation,
                    catalog_items=ctx.catalog_items,
                    catalog_retrieval_attempted=ctx.catalog_retrieval_attempted,
                    storage=get_storage_provider(),
                    text_message=response_msg,
                )
                if decision.should_send:
                    deliver_catalog_media_image(
                        db=db,
                        workspace_id=workspace_id,
                        conversation=conversation,
                        decision=decision,
                        agent_id=agent.id,
                    )
            except Exception:
                logger.exception(
                    "catalog_media_delivery unexpected error conversation=%s",
                    conversation.id,
                )

        # After text (+ optional catalog image) delivery: reply with a
        # synthesized voice message when the triggering message was itself a
        # voice note — whatsapp-voice-groq-elevenlabs-prd.md. Same
        # "text/catalog image first, voice second" pattern; the text message
        # always stays as the source of truth for Inbox/Auditoria, voice is
        # an addition, never a replacement.
        if text_delivered and getattr(trigger_message, "content_type", None) == "audio":
            _maybe_deliver_voice_reply(
                db,
                workspace_id=workspace_id,
                conversation=conversation,
                agent=agent,
                reply_text=reply_content,
            )

    return run


# ── Internal helpers ──────────────────────────────────────────────────────────


def _build_image_content_block(trigger_message: ConversationMessage) -> dict | None:
    """
    Fetch the stored image bytes and build an Anthropic vision content block.

    Returns None if the image can't be read back from storage — callers must
    fall back to a text-only turn (with a note that the image was unreadable)
    rather than crash the whole reply.
    """
    from app.services.storage.factory import get_storage_provider  # noqa: PLC0415

    mime_type = (trigger_message.metadata_json or {}).get("media_mime_type") or "image/jpeg"
    try:
        storage = get_storage_provider()
        data = storage.get_file(trigger_message.media_url)
    except Exception:
        logger.exception(
            "conversation_agent_reply image fetch failed message_id=%s",
            trigger_message.id,
        )
        return None

    encoded = base64.b64encode(data).decode("ascii")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": mime_type, "data": encoded},
    }


def _maybe_deliver_voice_reply(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    agent: Agent,
    reply_text: str,
) -> None:
    """
    Synthesize the text reply as speech and deliver it as a second, separate
    WhatsApp message — whatsapp-voice-groq-elevenlabs-prd.md.

    Best-effort and silent on any missing precondition (toggle off, no voice
    configured, no ElevenLabs key) or failure (synthesis, storage, delivery)
    — a voice reply is always additive to the already-sent text reply, never
    a requirement for it.
    """
    prompt_cfg = db.scalar(
        select(AgentPromptSettings).where(AgentPromptSettings.agent_id == agent.id)
    )
    if (
        prompt_cfg is None
        or not prompt_cfg.voice_reply_enabled
        or not prompt_cfg.elevenlabs_voice_id
    ):
        return

    from app.services.workspace_credentials_service import get_workspace_credential  # noqa: PLC0415

    elevenlabs_key = get_workspace_credential(db, workspace_id, "elevenlabs")
    if not elevenlabs_key:
        return

    from app.services.elevenlabs_voice_service import synthesize_speech  # noqa: PLC0415

    audio_bytes = synthesize_speech(elevenlabs_key, reply_text, prompt_cfg.elevenlabs_voice_id)
    if not audio_bytes:
        return

    from app.services.storage.factory import get_storage_provider  # noqa: PLC0415

    storage_key = f"conversation-media/{workspace_id}/{uuid.uuid4()}.mp3"
    try:
        get_storage_provider().put_file(storage_key, audio_bytes, content_type="audio/mpeg")
    except Exception:
        logger.exception("voice_reply storage write failed conversation=%s", conversation.id)
        return

    voice_msg = ConversationMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        direction="outbound",
        sender_type="agent",
        agent_id=agent.id,
        content="[Mensagem de voz]",
        content_type="audio",
        media_url=storage_key,
        metadata_json={"media_mime_type": "audio/mpeg"},
    )
    db.add(voice_msg)
    db.commit()
    db.refresh(voice_msg)

    from app.services.messaging import deliver_media_message  # noqa: PLC0415

    try:
        deliver_media_message(
            db, voice_msg, conversation, storage_key=storage_key, mime_type="audio/mpeg"
        )
    except Exception:
        logger.exception(
            "voice_reply delivery failed conversation=%s message=%s",
            conversation.id,
            voice_msg.id,
        )


def _save_run(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    conversation: Conversation,
    trigger_message: ConversationMessage,
    agent: Agent,
    model: AiModel | None,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    rag_used: bool = False,
    retrieved_chunks_count: int = 0,
    retrieval_duration_ms: int | None = None,
) -> ConversationAgentRun:
    """Persist a non-success run and commit."""
    logger.info(
        "agent_reply_run status=%s error_code=%s conversation_id=%s error=%s",
        status,
        error_code,
        conversation.id,
        error_message,
    )
    run = ConversationAgentRun(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        trigger_message_id=trigger_message.id,
        response_message_id=None,
        agent_id=agent.id,
        ai_model_id=model.id if model is not None else None,
        status=status,
        credits_used=0,
        rag_used=rag_used,
        retrieved_chunks_count=retrieved_chunks_count,
        retrieval_duration_ms=retrieval_duration_ms,
        error_code=error_code,
        error_message=error_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _get_workspace_plan_code(db: Session, workspace_id: uuid.UUID) -> str:
    from app.enums import SubscriptionStatus

    sub = db.scalar(
        select(WorkspaceSubscription).where(
            WorkspaceSubscription.workspace_id == workspace_id,
            WorkspaceSubscription.status == SubscriptionStatus.active.value,
        )
    )
    if sub is None:
        return "starter"
    plan = db.scalar(select(Plan).where(Plan.id == sub.plan_id))
    return plan.code if plan else "starter"


def _get_usage_counter(db: Session, workspace_id: uuid.UUID) -> UsageCounter | None:
    from app.services.plan_service import get_or_create_usage_counter  # noqa: PLC0415

    try:
        return get_or_create_usage_counter(db, workspace_id)
    except Exception:
        return None


def _has_credits(
    db: Session,
    counter: UsageCounter,
    credits_needed: int,
    plan_code: str,
) -> bool:
    plan = db.scalar(select(Plan).where(Plan.code == plan_code))
    monthly_limit = plan.monthly_ai_credits if plan else 0
    return counter.ai_credits_used + credits_needed <= monthly_limit


def _increment_credits(db: Session, workspace_id: uuid.UUID, credits: int) -> None:
    """Atomic in-place increment — safe against concurrent requests."""
    now = datetime.now(timezone.utc)
    db.execute(
        update(UsageCounter)
        .where(
            UsageCounter.workspace_id == workspace_id,
            UsageCounter.period_start <= now,
            UsageCounter.period_end >= now,
        )
        .values(ai_credits_used=UsageCounter.ai_credits_used + credits)
    )
