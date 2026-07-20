"""
Agent Tools service — CRUD for `agent_tools` plus the pieces that turn a
row into something the LLM tool-calling loop can actually use:

- build_tool_schema(): AgentTool -> Anthropic tool schema (name/description/input_schema)
- build_tool_dispatch(): list[AgentTool] -> {name: executor} for agent_llm_executor.run_agent_turn
- execute_http_tool(): tool_type="http_request" (Fase 4 of the tool-calling PRD) —
  a synchronous, SSRF-safe outbound HTTP call.
- execute_request_human_tool(): tool_type="request_human" (request-human-tool-prd.md) —
  pauses the AI on the conversation and notifies workspace admins by email.
- execute_mark_resolved_tool(): tool_type="mark_resolved" (mark-resolved-tool-prd.md) —
  sets the conversation to status="resolved" with a summary.
- execute_capture_contact_data_tool(): tool_type="capture_contact_data"
  (agent-tools-batch-2-prd.md) — upserts ContactVariable rows.
- execute_pipeline_action_tool(): tool_type="pipeline_action"
  (agent-tools-batch-2-prd.md) — creates/moves the conversation's PipelineEntry
  to an operator-fixed target stage.
- execute_assign_operator_tool(): tool_type="assign_operator"
  (agent-tools-batch-2-prd.md) — assigns the conversation to an operator-fixed
  team member and notifies them by email.

The CRUD functions and build_tool_schema/build_tool_dispatch are written
generically so a future tool type plugs in without reshaping this module.
"""

import json
import logging
import re
import uuid
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import MemberRole, MemberStatus
from app.models.agent import Agent
from app.models.agent_tool import AgentTool
from app.models.conversation import Conversation
from app.models.pipeline import Pipeline
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.agent_tool import (
    AgentToolConfig,
    AgentToolCreate,
    AgentToolUpdate,
    AssignOperatorToolConfig,
    CaptureContactDataToolConfig,
    HttpToolConfig,
    MarkResolvedToolConfig,
    PipelineActionToolConfig,
    RequestHumanToolConfig,
)
from app.services.agent_llm_executor import ToolExecutor
from app.services.pipeline_webhook_service import WebhookUrlError, validate_webhook_url

logger = logging.getLogger(__name__)

# HTTP tool calls are synchronous and block the user-facing turn — keep this
# short. Unlike the Pipeline stage webhook (fire-and-forget, one retry), a
# slow/unreachable endpoint here directly delays the agent's reply, so there
# is no retry: fail fast and let the model react (Fase 5 of the PRD is where
# the tool-result guardrail/UX around that lives).
_MAX_RESPONSE_CHARS = 4000

# Matches {cep}, {order_id}, etc. in a configured URL — the operator writes
# these in the URL field, the model fills them in at call time. Deliberately
# restricted to identifier-like names (no `{}` with slashes/dots/etc.) so
# extraction can't be confused by anything else that happens to contain braces.
_URL_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_agent_tools(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> list[AgentTool]:
    _get_agent_or_404(db, workspace_id, agent_id)
    return list(
        db.scalars(
            select(AgentTool)
            .where(AgentTool.agent_id == agent_id, AgentTool.workspace_id == workspace_id)
            .order_by(AgentTool.sort_order, AgentTool.created_at)
        ).all()
    )


def create_agent_tool(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID, data: AgentToolCreate
) -> AgentTool:
    _get_agent_or_404(db, workspace_id, agent_id)
    _validate_tool_config(db, workspace_id, data.tool_type, data.config)

    existing = db.scalar(
        select(AgentTool).where(AgentTool.agent_id == agent_id, AgentTool.name == data.name)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Já existe uma ferramenta chamada '{data.name}' neste agente.",
        )

    tool = AgentTool(
        workspace_id=workspace_id,
        agent_id=agent_id,
        tool_type=data.tool_type,
        name=data.name,
        description=data.description,
        is_enabled=data.is_enabled,
        # mode="json" matters: PipelineActionToolConfig/AssignOperatorToolConfig
        # have UUID fields, and a bare model_dump() leaves raw UUID objects that
        # the JSONB column's JSON serializer can't encode.
        config=data.config.model_dump(mode="json"),
        sort_order=data.sort_order,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


def update_agent_tool(
    db: Session,
    workspace_id: uuid.UUID,
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    data: AgentToolUpdate,
) -> AgentTool:
    _get_agent_or_404(db, workspace_id, agent_id)
    tool = _get_tool_or_404(db, workspace_id, agent_id, tool_id)

    if data.config is not None:
        _validate_tool_config(db, workspace_id, tool.tool_type, data.config)
        tool.config = data.config.model_dump(mode="json")
    if data.name is not None and data.name != tool.name:
        existing = db.scalar(
            select(AgentTool).where(
                AgentTool.agent_id == agent_id, AgentTool.name == data.name, AgentTool.id != tool_id
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Já existe uma ferramenta chamada '{data.name}' neste agente.",
            )
        tool.name = data.name
    if data.description is not None:
        tool.description = data.description
    if data.is_enabled is not None:
        tool.is_enabled = data.is_enabled
    if data.sort_order is not None:
        tool.sort_order = data.sort_order

    db.commit()
    db.refresh(tool)
    return tool


def delete_agent_tool(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID, tool_id: uuid.UUID
) -> None:
    _get_agent_or_404(db, workspace_id, agent_id)
    tool = _get_tool_or_404(db, workspace_id, agent_id, tool_id)
    db.delete(tool)
    db.commit()


def get_enabled_tools_for_agent(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID
) -> list[AgentTool]:
    """Used by the reply/test services to build the LLM `tools=` list — no 404s,
    an agent with no enabled tools just returns an empty list."""
    return list(
        db.scalars(
            select(AgentTool).where(
                AgentTool.agent_id == agent_id,
                AgentTool.workspace_id == workspace_id,
                AgentTool.is_enabled.is_(True),
            ).order_by(AgentTool.sort_order, AgentTool.created_at)
        ).all()
    )


# ── LLM-facing schema + dispatch ────────────────────────────────────────────────

def build_tool_schema(tool: AgentTool) -> dict:
    """AgentTool -> the dict shape LLMRequest.tools expects (Anthropic tool schema)."""
    if tool.tool_type == "http_request":
        url_params = _URL_PLACEHOLDER_RE.findall(tool.config.get("url", ""))
        path_descriptions = tool.config.get("path_param_descriptions") or {}
        properties: dict = {
            name: {
                "type": "string",
                "description": (
                    path_descriptions.get(name)
                    or f"Value for '{name}', used in the request URL."
                ),
            }
            for name in url_params
        }
        query_param_specs = tool.config.get("query_params") or []
        if query_param_specs:
            # Operator documented specific query params (http-tool-ux-improvements-prd.md) —
            # give the model a named/described nested schema instead of a blind object.
            query_properties = {
                spec["name"]: {
                    "type": "string",
                    "description": spec.get("description") or f"Query param '{spec['name']}'.",
                }
                for spec in query_param_specs
            }
            required_query = [spec["name"] for spec in query_param_specs if spec.get("required")]
            query_schema: dict = {
                "type": "object",
                "description": "Query string parameters for this request.",
                "properties": query_properties,
            }
            if required_query:
                query_schema["required"] = required_query
            properties["query_params"] = query_schema
        else:
            properties["query_params"] = {
                "type": "object",
                "description": "Optional query string parameters to add to the request.",
            }
        body_template = tool.config.get("body_template")
        body_params: list[str] = []
        if body_template:
            # Structured body (http-tool-body-template-prd.md) — the operator
            # wrote the literal JSON, {placeholder} marks where model-supplied
            # values go (even inside nested objects like Cal.com's `attendee`).
            # Named/described properties instead of a blind "body" object —
            # same rationale as query_params/path vars.
            body_descriptions = tool.config.get("body_param_descriptions") or {}
            body_params = _URL_PLACEHOLDER_RE.findall(body_template)
            for name in body_params:
                properties[name] = {
                    "type": "string",
                    "description": (
                        body_descriptions.get(name)
                        or f"Value for '{name}', used in the request body."
                    ),
                }
        else:
            properties["body"] = {
                "type": "object",
                "description": "Optional JSON body (used for POST/PUT/PATCH only).",
            }
        input_schema: dict = {"type": "object", "properties": properties}
        required = list(dict.fromkeys([*url_params, *body_params]))  # de-duped, order-preserved
        if required:
            input_schema["required"] = required
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": input_schema,
        }
    if tool.tool_type == "request_human":
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": (
                            "Motivo pelo qual o atendimento está sendo transferido "
                            "para um humano."
                        ),
                    }
                },
                "required": ["reason"],
            },
        }
    if tool.tool_type == "mark_resolved":
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "resolution_summary": {
                        "type": "string",
                        "description": (
                            "Resumo curto de como o problema do cliente foi resolvido."
                        ),
                    }
                },
                "required": ["resolution_summary"],
            },
        }
    if tool.tool_type == "capture_contact_data":
        # Every field is optional — the model captures whatever it's confident
        # about, whenever it appears in the conversation; no field is required
        # on any single call (agent-tools-batch-2-prd.md).
        fields = tool.config.get("fields") or []
        properties = {
            f["key"]: {
                "type": "string",
                "description": f.get("description") or f"Value for '{f['key']}'.",
            }
            for f in fields
        }
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {"type": "object", "properties": properties},
        }
    if tool.tool_type == "pipeline_action":
        # Pure toggle — the target pipeline/stage is fixed by the operator in
        # config, the model only ever decides *when* to call it, zero input.
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {"type": "object", "properties": {}},
        }
    if tool.tool_type == "assign_operator":
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": (
                            "Motivo pelo qual o atendimento está sendo atribuído a esse operador."
                        ),
                    }
                },
                "required": ["reason"],
            },
        }
    raise ValueError(f"Unknown tool_type: {tool.tool_type!r}")


def build_tool_dispatch(
    tools: list[AgentTool],
    *,
    db: Session | None = None,
    workspace_id: uuid.UUID | None = None,
    conversation: Conversation | None = None,
) -> dict[str, ToolExecutor]:
    """
    list[AgentTool] -> {name: executor} for agent_llm_executor.run_agent_turn.

    *db*/*workspace_id*/*conversation* are only needed by tool_type="request_human"
    (it mutates the conversation and sends an email — unlike the HTTP tool, which
    is a pure function of its config+input). Callers that only ever attach
    "http_request" tools (none today, but future-proof) can omit them.
    When *conversation* is None (the Playground has no real conversation row),
    the request_human executor runs in simulation mode — no side effects.
    """
    dispatch: dict[str, ToolExecutor] = {}
    for tool in tools:
        if tool.tool_type == "http_request":
            config = tool.config  # already validated JSONB, safe to trust shape here
            dispatch[tool.name] = _make_http_executor(config)
        elif tool.tool_type == "request_human":
            dispatch[tool.name] = _make_request_human_executor(
                db=db, workspace_id=workspace_id, conversation=conversation
            )
        elif tool.tool_type == "mark_resolved":
            dispatch[tool.name] = _make_mark_resolved_executor(
                db=db, workspace_id=workspace_id, conversation=conversation
            )
        elif tool.tool_type == "capture_contact_data":
            config = tool.config
            identity_map = {
                f["key"]: f["maps_to"]
                for f in config.get("fields", [])
                if f.get("maps_to")
            }
            dispatch[tool.name] = _make_capture_contact_data_executor(
                db=db, workspace_id=workspace_id, conversation=conversation,
                identity_map=identity_map,
            )
        elif tool.tool_type == "pipeline_action":
            config = tool.config
            dispatch[tool.name] = _make_pipeline_action_executor(
                db=db, workspace_id=workspace_id, conversation=conversation,
                pipeline_id=config.get("pipeline_id"), stage_id=config.get("stage_id"),
            )
        elif tool.tool_type == "assign_operator":
            config = tool.config
            dispatch[tool.name] = _make_assign_operator_executor(
                db=db, workspace_id=workspace_id, conversation=conversation,
                user_id=config.get("user_id"),
            )
    return dispatch


def _make_http_executor(config: dict) -> ToolExecutor:
    def executor(input_: dict) -> str:
        return execute_http_tool(config, input_)
    return executor


def _make_request_human_executor(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
) -> ToolExecutor:
    def executor(input_: dict) -> str:
        reason = str(input_.get("reason") or "Motivo não informado.")
        return execute_request_human_tool(
            db=db, workspace_id=workspace_id, conversation=conversation, reason=reason
        )
    return executor


def _make_mark_resolved_executor(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
) -> ToolExecutor:
    def executor(input_: dict) -> str:
        summary = str(input_.get("resolution_summary") or "Resumo não informado.")
        return execute_mark_resolved_tool(
            db=db, workspace_id=workspace_id, conversation=conversation,
            resolution_summary=summary,
        )
    return executor


def _make_capture_contact_data_executor(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    identity_map: dict[str, str],
) -> ToolExecutor:
    def executor(input_: dict) -> str:
        captured = {k: str(v) for k, v in input_.items() if v is not None and str(v).strip()}
        return execute_capture_contact_data_tool(
            db=db, workspace_id=workspace_id, conversation=conversation, captured_fields=captured,
            identity_map=identity_map,
        )
    return executor


def _make_pipeline_action_executor(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    pipeline_id: str | None,
    stage_id: str | None,
) -> ToolExecutor:
    def executor(_input: dict) -> str:
        return execute_pipeline_action_tool(
            db=db, workspace_id=workspace_id, conversation=conversation,
            pipeline_id=uuid.UUID(pipeline_id) if pipeline_id else None,
            stage_id=uuid.UUID(stage_id) if stage_id else None,
        )
    return executor


def _make_assign_operator_executor(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    user_id: str | None,
) -> ToolExecutor:
    def executor(input_: dict) -> str:
        reason = str(input_.get("reason") or "Motivo não informado.")
        return execute_assign_operator_tool(
            db=db, workspace_id=workspace_id, conversation=conversation,
            user_id=uuid.UUID(user_id) if user_id else None, reason=reason,
        )
    return executor


# ── HTTP tool execution ──────────────────────────────────────────────────────────

def _substitute_url_placeholders(url_template: str, input_: dict) -> str:
    """
    Fill {name} placeholders in *url_template* with values from *input_*.

    Every substituted value is percent-encoded with safe="" — meaning even a
    "/", "?", "#", or "://" supplied by the model becomes a literal encoded
    path segment, never a way to escape the configured path or point the
    request at a different host. The host/scheme come only from the operator-
    configured template and are never influenced by model input.
    """
    def replacer(match: re.Match) -> str:
        name = match.group(1)
        value = input_.get(name)
        if value is None:
            raise ValueError(f"Missing required URL parameter: '{name}'")
        return quote(str(value), safe="")

    return _URL_PLACEHOLDER_RE.sub(replacer, url_template)


def _substitute_body_placeholders(body_template: str, input_: dict) -> dict:
    """
    Fill {name} placeholders inside *body_template* (a JSON string the
    operator wrote, e.g. '{"attendee": {"name": "{name}", "email": "{email}"}}')
    with values from *input_*, then parse the result as JSON.

    Placeholders always sit inside quotes the operator already wrote in the
    template — so substitution only needs to escape the value's *content* as
    JSON-string text; json.dumps(value)[1:-1] produces exactly that (a fully
    quoted+escaped JSON string literal, with the outer quotes stripped back
    off). Unlike URL substitution (which percent-encodes because raw
    slashes/hosts are dangerous there), there's no equivalent injection risk
    here: a value containing '", "evil": "true' becomes one escaped string —
    every quote/backslash inside it is escaped before insertion, so it can
    only ever become string *content*, never new JSON keys/structure.

    Every value becomes a JSON string in the result (str(value) first) — a
    template can't produce a raw numeric/boolean field via a placeholder.
    Operator-fixed constants (e.g. a numeric eventTypeId) go straight in the
    template unquoted; only genuinely model-supplied values are placeholders.
    """
    def replacer(match: re.Match) -> str:
        name = match.group(1)
        value = input_.get(name)
        if value is None:
            raise ValueError(f"Missing required body parameter: '{name}'")
        return json.dumps(str(value))[1:-1]

    substituted = _URL_PLACEHOLDER_RE.sub(replacer, body_template)
    try:
        return json.loads(substituted)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Configured body_template did not produce valid JSON after substitution: {exc}"
        ) from exc


def execute_http_tool(config: dict, input_: dict) -> str:
    """
    Synchronously call the configured endpoint. *config* is the tool's fixed
    setup (method/url template/headers/timeout); *input_* is whatever the
    model decided to send this call (URL placeholder values/query_params/body).

    Raises on any failure — agent_llm_executor.run_agent_turn already catches
    exceptions from a tool executor and reports them to the model as a tool
    error, so this function does not need its own try/except-and-swallow.

    A non-2xx response raises ToolCallFailedError (message = the same JSON
    a success would have returned) instead of returning normally — httpx
    doesn't raise on 4xx/5xx by default, and without this a real failure
    (e.g. Cal.com rejecting the call) would be indistinguishable from a
    success in the tool-call audit trail. The model still sees the exact
    same status_code + body either way; only the recorded status changes.
    """
    url = _substitute_url_placeholders(config["url"], input_)
    # Re-validate the URL *after* substitution — defense in depth alongside
    # the percent-encoding above, and consistent with re-validating at send
    # time everywhere else in this codebase (DNS rebinding protection).
    validate_webhook_url(url)

    query_params = input_.get("query_params") or {}
    if query_params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(query_params)}"

    headers = dict(config.get("headers") or {})
    method = config.get("method", "GET")

    json_body = None
    if method in ("POST", "PUT", "PATCH"):
        body_template = config.get("body_template")
        if body_template:
            json_body = _substitute_body_placeholders(body_template, input_)
            headers.setdefault("Content-Type", "application/json")
        else:
            body = input_.get("body")
            if body is not None:
                json_body = body
                headers.setdefault("Content-Type", "application/json")

    timeout = config.get("timeout_seconds", 8)

    response = httpx.request(
        method, url, headers=headers, json=json_body, timeout=timeout
    )
    text = response.text[:_MAX_RESPONSE_CHARS]
    result = json.dumps({"status_code": response.status_code, "body": text})
    if response.status_code >= 400:
        from app.services.agent_llm_executor import ToolCallFailedError  # noqa: PLC0415
        raise ToolCallFailedError(result)
    return result


def validate_http_tool_config(config: dict, sample_input: dict) -> dict:
    """
    "Validar Configuração" (http-tool-ux-improvements-prd.md) — run execute_http_tool
    against a *draft* config (no AgentTool row needs to exist yet) and report the
    result as data instead of letting the caller's exception propagate. Used by the
    /tools/http/test endpoint so a bad URL/header/timeout shows up in the config
    modal immediately, not after saving + activating + waiting for a real trigger.

    A non-2xx response is still reported as `ok: True` with the real status
    code/body — for a human testing their own config, "it responded with
    400" is useful diagnostic data, not a failure of the test mechanism
    itself (ToolCallFailedError only changes how agent_llm_executor's audit
    trail records the call, not this endpoint's response shape).
    """
    from app.services.agent_llm_executor import ToolCallFailedError  # noqa: PLC0415
    try:
        raw = execute_http_tool(config, sample_input)
        parsed = json.loads(raw)
        return {"ok": True, "status_code": parsed.get("status_code"), "body": parsed.get("body")}
    except ToolCallFailedError as exc:
        parsed = json.loads(str(exc))
        return {"ok": True, "status_code": parsed.get("status_code"), "body": parsed.get("body")}
    except Exception as exc:  # noqa: BLE001 — this is a user-facing "did it work?" check
        return {"ok": False, "error": str(exc)}


# ── Request-human tool execution ────────────────────────────────────────────────

def execute_request_human_tool(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    reason: str,
) -> str:
    """
    Pause the AI on *conversation* and best-effort notify workspace admins.

    Playground mode: when *conversation* is None (no real conversation row —
    a Playground test session, not an Inbox conversation), this never touches
    the database or sends an email; it just tells the model what would happen
    in a real conversation, so testing an agent doesn't spam the team's inbox.

    Idempotent within a turn: the tool-calling loop allows the model to call
    this more than once before producing a final answer (e.g. it changes its
    mind about the reason) — only the first call actually pauses the AI and
    sends the notification; subsequent calls in the same turn are a no-op.
    """
    if conversation is None:
        return (
            "[Simulação de Playground] Em uma conversa real, isso pausaria a IA "
            f"e notificaria a equipe por e-mail. Motivo: {reason}"
        )

    assert db is not None and workspace_id is not None  # always set alongside a real conversation

    if not conversation.ai_enabled:
        return "O atendimento já havia sido transferido para um humano nesta conversa."

    conversation.ai_enabled = False
    conversation.handoff_reason = reason[:500]
    db.flush()

    try:
        _notify_handoff_requested(
            db, workspace_id=workspace_id, conversation=conversation, reason=reason
        )
    except Exception:
        logger.exception(
            "request_human_notify_failed workspace_id=%s conversation_id=%s",
            workspace_id, conversation.id,
        )

    return (
        "Atendimento transferido para um humano com sucesso. A equipe foi notificada. "
        "Informe o cliente de forma breve e educada que alguém vai continuar o atendimento."
    )


def _notify_handoff_requested(
    db: Session, *, workspace_id: uuid.UUID, conversation: Conversation, reason: str
) -> None:
    """Best-effort email to workspace owners/admins. Never raises to the caller."""
    from app.services.email_service import get_email_service  # noqa: PLC0415
    from app.services.email_templates import (  # noqa: PLC0415
        handoff_requested_email_html,
        handoff_requested_email_text,
    )

    recipients = _get_workspace_notify_recipients(db, workspace_id)
    if not recipients:
        return

    contact_name = None
    if conversation.contact_id is not None:
        from app.models.contact import Contact  # noqa: PLC0415
        contact_name = db.scalar(
            select(Contact.name).where(Contact.id == conversation.contact_id)
        )

    conversation_url = f"{settings.app_url}/dashboard/inbox?conversation={conversation.id}"
    html = handoff_requested_email_html(
        contact_name=contact_name, reason=reason, conversation_url=conversation_url
    )
    text = handoff_requested_email_text(
        contact_name=contact_name, reason=reason, conversation_url=conversation_url
    )

    email_service = get_email_service()
    for email, _name in recipients:
        email_service.send(
            to=email,
            subject="Um cliente está esperando atendimento humano — Wenzap",
            html=html,
            text=text,
        )


def _get_workspace_notify_recipients(
    db: Session, workspace_id: uuid.UUID
) -> list[tuple[str, str | None]]:
    """Active owner/admin members of the workspace — who should hear about a handoff."""
    rows = db.execute(
        select(User.email, User.name)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role.in_([MemberRole.owner.value, MemberRole.admin.value]),
            WorkspaceMember.status == MemberStatus.active.value,
        )
    ).all()
    return [(email, name) for email, name in rows]


#  RequestHumanToolConfig and MarkResolvedToolConfig are structurally
#  identical (both empty, extra="forbid") — Pydantic's smart union can
#  resolve an incoming `{}` to either class regardless of which tool_type
#  it's actually for. Harmless (they behave identically), but means we must
#  check membership in this tuple, not isinstance against one specific class.
_EMPTY_TOOL_CONFIG_TYPES = (RequestHumanToolConfig, MarkResolvedToolConfig)


# ── Mark-resolved tool execution ────────────────────────────────────────────────

def execute_mark_resolved_tool(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    resolution_summary: str,
) -> str:
    """
    Set *conversation* to status="resolved" with a summary (mark-resolved-tool-prd.md).

    Same end state as a human manually picking "Resolvida" in the Inbox status
    dropdown — does NOT touch ai_enabled/assigned_user_id. Playground mode
    (conversation is None) simulates without side effects, same as the other
    two tools. Idempotent within a turn: a second call in the same turn (model
    changes its mind about the summary) is a no-op once already resolved.

    Every non-simulation return explicitly tells the model to keep talking
    to the customer — see execute_pipeline_action_tool's docstring for why
    (a bare "done" result risks an empty, undeliverable final reply).
    """
    if conversation is None:
        return (
            "[Simulação de Playground] Em uma conversa real, isso marcaria a conversa "
            f"como resolvida. Resumo: {resolution_summary}"
        )

    assert db is not None and workspace_id is not None

    if conversation.status == "resolved":
        return (
            "A conversa já estava marcada como resolvida. Continue a conversa "
            "normalmente com o cliente."
        )

    conversation.status = "resolved"
    conversation.resolution_summary = resolution_summary[:500]
    db.flush()

    return (
        "Conversa marcada como resolvida com sucesso. Informe o cliente de forma "
        "breve e educada que o atendimento foi concluído."
    )


# ── Capture-contact-data tool execution ─────────────────────────────────────────

def execute_capture_contact_data_tool(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    captured_fields: dict[str, str],
    identity_map: dict[str, str] | None = None,
) -> str:
    """
    Upsert one ContactVariable row per captured field (agent-tools-batch-2-prd.md).

    Not idempotency-guarded like the other tools — upserting is safe to call
    repeatedly as more data trickles in across the conversation (each call
    only ever touches the keys it actually captured this turn).

    `identity_map` (capture-contact-identity-sync-prd.md) additionally syncs
    captured keys the operator marked as the contact's name/phone/email into
    the structured Contact columns — not just the variable.
    """
    if conversation is None:
        keys = ", ".join(captured_fields) or "nenhum"
        return f"[Simulação de Playground] Em uma conversa real, isso salvaria: {keys}."

    assert db is not None and workspace_id is not None

    if not captured_fields:
        return "Nenhum dado novo para salvar."

    if conversation.contact_id is None:
        return "Não há um contato associado a esta conversa — nada foi salvo."

    from app.schemas.contact import ContactUpdate  # noqa: PLC0415
    from app.services.contact_service import (  # noqa: PLC0415
        update_contact,
        upsert_contact_variable,
    )

    for key, value in captured_fields.items():
        upsert_contact_variable(
            db, workspace_id, conversation.contact_id, key, value[:2000], source="ai"
        )

    identity_updated: list[str] = []
    for key, field_name in (identity_map or {}).items():
        value = captured_fields.get(key)
        if not value:
            continue
        try:
            update_contact(
                db, workspace_id, conversation.contact_id,
                ContactUpdate(**{field_name: value}),
            )
            identity_updated.append(field_name)
        except HTTPException:
            # Dedup conflict (phone/email already belongs to another contact
            # in the workspace) — the variable above is already saved; skip
            # this field instead of failing the whole tool call over it.
            pass

    message = f"Dados salvos no contato: {', '.join(captured_fields)}."
    if identity_updated:
        message += f" Contato atualizado: {', '.join(identity_updated)}."
    return message


# ── Pipeline-action tool execution ──────────────────────────────────────────────

def execute_pipeline_action_tool(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    pipeline_id: uuid.UUID | None,
    stage_id: uuid.UUID | None,
) -> str:
    """
    Move (or create) the conversation's PipelineEntry to the operator-fixed
    target stage (agent-tools-batch-2-prd.md). Reuses pipeline_service's
    create_entry/move_entry unchanged — find-or-create by (pipeline_id,
    conversation_id), same lookup ensure_conversation_pipeline_entry() uses.

    Every non-simulation return explicitly tells the model to keep talking
    to the customer — found in production (2026-07-18) that a bare "done"
    result with no such instruction can make the model treat the tool call
    itself as the whole turn and end up with an empty final reply, which
    then fails to send (WhatsApp providers reject empty text messages).
    """
    if conversation is None:
        return (
            "[Simulação de Playground] Em uma conversa real, isso moveria o card "
            "desta conversa no pipeline configurado."
        )

    assert db is not None and workspace_id is not None and pipeline_id and stage_id

    from app.schemas.pipeline import PipelineEntryCreate, PipelineEntryMove  # noqa: PLC0415
    from app.services import pipeline_service  # noqa: PLC0415

    existing = db.scalar(
        select(PipelineEntry).where(
            PipelineEntry.pipeline_id == pipeline_id,
            PipelineEntry.conversation_id == conversation.id,
        )
    )
    if existing is not None:
        if existing.stage_id == stage_id:
            return (
                "O card já estava nessa etapa do pipeline. Continue a conversa "
                "normalmente com o cliente."
            )
        pipeline_service.move_entry(
            db, workspace_id, pipeline_id, existing.id, PipelineEntryMove(stage_id=stage_id)
        )
    else:
        pipeline_service.create_entry(
            db, workspace_id, pipeline_id,
            PipelineEntryCreate(conversation_id=conversation.id, stage_id=stage_id),
        )

    return (
        "Card do pipeline atualizado com sucesso. Continue a conversa "
        "normalmente com o cliente."
    )


# ── Assign-operator tool execution ──────────────────────────────────────────────

def execute_assign_operator_tool(
    *,
    db: Session | None,
    workspace_id: uuid.UUID | None,
    conversation: Conversation | None,
    user_id: uuid.UUID | None,
    reason: str,
) -> str:
    """
    Assign *conversation* to the operator-fixed *user_id*, same end state as
    a human manually clicking "Assumir" (assigned_user_id + ai_enabled=False),
    plus a captured reason and a best-effort email to that ONE operator
    (unlike request_human, which broadcasts to every owner/admin — here we
    already know exactly who should look).

    Idempotent: if the conversation already has any assignee, does nothing
    (whoever is already on it takes priority over a second tool call).
    """
    if conversation is None:
        return (
            "[Simulação de Playground] Em uma conversa real, isso atribuiria a conversa "
            f"ao operador configurado. Motivo: {reason}"
        )

    assert db is not None and workspace_id is not None and user_id is not None

    if conversation.assigned_user_id is not None:
        return "A conversa já está atribuída a um operador."

    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == MemberStatus.active.value,
        )
    )
    if member is None:
        return "O operador configurado não está mais disponível neste workspace."

    conversation.assigned_user_id = user_id
    conversation.ai_enabled = False
    conversation.assignment_reason = reason[:500]
    db.flush()

    try:
        _notify_operator_assigned(
            db, workspace_id=workspace_id, conversation=conversation,
            user_id=user_id, reason=reason,
        )
    except Exception:
        logger.exception(
            "assign_operator_notify_failed workspace_id=%s conversation_id=%s",
            workspace_id, conversation.id,
        )

    return (
        "Atendimento atribuído ao operador com sucesso. Ele foi notificado por e-mail. "
        "Informe o cliente de forma breve e educada que alguém vai continuar o atendimento."
    )


def _notify_operator_assigned(
    db: Session, *, workspace_id: uuid.UUID, conversation: Conversation,
    user_id: uuid.UUID, reason: str,
) -> None:
    """Best-effort email to the ONE assigned operator. Never raises to the caller."""
    from app.services.email_service import get_email_service  # noqa: PLC0415
    from app.services.email_templates import (  # noqa: PLC0415
        operator_assigned_email_html,
        operator_assigned_email_text,
    )

    recipient = db.scalar(select(User.email).where(User.id == user_id))
    if not recipient:
        return

    contact_name = None
    if conversation.contact_id is not None:
        from app.models.contact import Contact  # noqa: PLC0415
        contact_name = db.scalar(
            select(Contact.name).where(Contact.id == conversation.contact_id)
        )

    conversation_url = f"{settings.app_url}/dashboard/inbox?conversation={conversation.id}"
    html = operator_assigned_email_html(
        contact_name=contact_name, reason=reason, conversation_url=conversation_url
    )
    text = operator_assigned_email_text(
        contact_name=contact_name, reason=reason, conversation_url=conversation_url
    )

    get_email_service().send(
        to=recipient,
        subject="Uma conversa foi atribuída a você — Wenzap",
        html=html,
        text=text,
    )


def _validate_tool_config(
    db: Session, workspace_id: uuid.UUID, tool_type: str, config: AgentToolConfig
) -> None:
    if tool_type == "http_request":
        if not isinstance(config, HttpToolConfig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config inválida para tool_type='http_request'.",
            )
        try:
            validate_webhook_url(config.url)
        except WebhookUrlError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    elif tool_type in ("request_human", "mark_resolved"):
        if not isinstance(config, _EMPTY_TOOL_CONFIG_TYPES):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Config inválida para tool_type='{tool_type}'.",
            )
    elif tool_type == "capture_contact_data":
        if not isinstance(config, CaptureContactDataToolConfig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config inválida para tool_type='capture_contact_data'.",
            )
        keys = [f.key for f in config.fields]
        if len(keys) != len(set(keys)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="As chaves dos campos devem ser únicas.",
            )
        maps_to_values = [f.maps_to for f in config.fields if f.maps_to is not None]
        if len(maps_to_values) != len(set(maps_to_values)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Só um campo pode ser mapeado para cada dado do contato (nome/telefone/e-mail).",
            )
    elif tool_type == "pipeline_action":
        if not isinstance(config, PipelineActionToolConfig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config inválida para tool_type='pipeline_action'.",
            )
        pipeline = db.scalar(
            select(Pipeline).where(
                Pipeline.id == config.pipeline_id, Pipeline.workspace_id == workspace_id
            )
        )
        if pipeline is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline não encontrado."
            )
        stage = db.scalar(
            select(PipelineStage).where(
                PipelineStage.id == config.stage_id,
                PipelineStage.pipeline_id == config.pipeline_id,
                PipelineStage.workspace_id == workspace_id,
            )
        )
        if stage is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Etapa não encontrada neste pipeline.",
            )
    elif tool_type == "assign_operator":
        if not isinstance(config, AssignOperatorToolConfig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config inválida para tool_type='assign_operator'.",
            )
        member = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == config.user_id,
                WorkspaceMember.status == MemberStatus.active.value,
            )
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O usuário selecionado não é um membro ativo deste workspace.",
            )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_agent_or_404(db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
    agent = db.scalar(
        select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado.")
    return agent


def _get_tool_or_404(
    db: Session, workspace_id: uuid.UUID, agent_id: uuid.UUID, tool_id: uuid.UUID
) -> AgentTool:
    tool = db.scalar(
        select(AgentTool).where(
            AgentTool.id == tool_id,
            AgentTool.agent_id == agent_id,
            AgentTool.workspace_id == workspace_id,
        )
    )
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ferramenta não encontrada."
        )
    return tool
