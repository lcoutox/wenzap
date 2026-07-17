"""
Agent Tools service — CRUD for `agent_tools` plus the pieces that turn a
row into something the LLM tool-calling loop can actually use:

- build_tool_schema(): AgentTool -> Anthropic tool schema (name/description/input_schema)
- build_tool_dispatch(): list[AgentTool] -> {name: executor} for agent_llm_executor.run_agent_turn
- execute_http_tool(): tool_type="http_request" (Fase 4 of the tool-calling PRD) —
  a synchronous, SSRF-safe outbound HTTP call.
- execute_request_human_tool(): tool_type="request_human" (request-human-tool-prd.md) —
  pauses the AI on the conversation and notifies workspace admins by email.

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
from app.models.user import User
from app.models.workspace_member import WorkspaceMember
from app.schemas.agent_tool import (
    AgentToolConfig,
    AgentToolCreate,
    AgentToolUpdate,
    HttpToolConfig,
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
    _validate_tool_config(data.tool_type, data.config)

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
        config=data.config.model_dump(),
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
        _validate_tool_config(tool.tool_type, data.config)
        tool.config = data.config.model_dump()
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
        properties["body"] = {
            "type": "object",
            "description": "Optional JSON body (used for POST/PUT/PATCH only).",
        }
        input_schema: dict = {"type": "object", "properties": properties}
        if url_params:
            input_schema["required"] = url_params
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


def execute_http_tool(config: dict, input_: dict) -> str:
    """
    Synchronously call the configured endpoint. *config* is the tool's fixed
    setup (method/url template/headers/timeout); *input_* is whatever the
    model decided to send this call (URL placeholder values/query_params/body).

    Raises on any failure — agent_llm_executor.run_agent_turn already catches
    exceptions from a tool executor and reports them to the model as a tool
    error, so this function does not need its own try/except-and-swallow.
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

    body = input_.get("body")
    json_body = None
    if body is not None and method in ("POST", "PUT", "PATCH"):
        json_body = body
        headers.setdefault("Content-Type", "application/json")

    timeout = config.get("timeout_seconds", 8)

    response = httpx.request(
        method, url, headers=headers, json=json_body, timeout=timeout
    )
    text = response.text[:_MAX_RESPONSE_CHARS]
    return json.dumps({"status_code": response.status_code, "body": text})


def validate_http_tool_config(config: dict, sample_input: dict) -> dict:
    """
    "Validar Configuração" (http-tool-ux-improvements-prd.md) — run execute_http_tool
    against a *draft* config (no AgentTool row needs to exist yet) and report the
    result as data instead of letting the caller's exception propagate. Used by the
    /tools/http/test endpoint so a bad URL/header/timeout shows up in the config
    modal immediately, not after saving + activating + waiting for a real trigger.
    """
    try:
        raw = execute_http_tool(config, sample_input)
        parsed = json.loads(raw)
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


def _validate_tool_config(tool_type: str, config: AgentToolConfig) -> None:
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
    elif tool_type == "request_human":
        if not isinstance(config, RequestHumanToolConfig):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config inválida para tool_type='request_human'.",
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
