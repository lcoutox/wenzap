"""
Agent Tools service — CRUD for `agent_tools` plus the pieces that turn a
row into something the LLM tool-calling loop can actually use:

- build_tool_schema(): AgentTool -> Anthropic tool schema (name/description/input_schema)
- build_tool_dispatch(): list[AgentTool] -> {name: executor} for agent_llm_executor.run_agent_turn
- execute_http_tool(): the only tool_type implemented so far (Fase 4 of the
  tool-calling PRD) — a synchronous, SSRF-safe outbound HTTP call.

Only tool_type="http_request" exists today; the CRUD functions and
build_tool_schema/build_tool_dispatch are written generically so a future
tool type (Calendar, Drive, etc.) plugs in without reshaping this module.
"""

import json
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_tool import AgentTool
from app.schemas.agent_tool import AgentToolCreate, AgentToolUpdate, HttpToolConfig
from app.services.agent_llm_executor import ToolExecutor
from app.services.pipeline_webhook_service import WebhookUrlError, validate_webhook_url

# HTTP tool calls are synchronous and block the user-facing turn — keep this
# short. Unlike the Pipeline stage webhook (fire-and-forget, one retry), a
# slow/unreachable endpoint here directly delays the agent's reply, so there
# is no retry: fail fast and let the model react (Fase 5 of the PRD is where
# the tool-result guardrail/UX around that lives).
_MAX_RESPONSE_CHARS = 4000


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
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "query_params": {
                        "type": "object",
                        "description": "Optional query string parameters to add to the request.",
                    },
                    "body": {
                        "type": "object",
                        "description": "Optional JSON body (used for POST/PUT/PATCH only).",
                    },
                },
            },
        }
    raise ValueError(f"Unknown tool_type: {tool.tool_type!r}")


def build_tool_dispatch(tools: list[AgentTool]) -> dict[str, ToolExecutor]:
    """list[AgentTool] -> {name: executor} for agent_llm_executor.run_agent_turn."""
    dispatch: dict[str, ToolExecutor] = {}
    for tool in tools:
        if tool.tool_type == "http_request":
            config = tool.config  # already validated JSONB, safe to trust shape here
            dispatch[tool.name] = _make_http_executor(config)
    return dispatch


def _make_http_executor(config: dict) -> ToolExecutor:
    def executor(input_: dict) -> str:
        return execute_http_tool(config, input_)
    return executor


# ── HTTP tool execution ──────────────────────────────────────────────────────────

def execute_http_tool(config: dict, input_: dict) -> str:
    """
    Synchronously call the configured endpoint. *config* is the tool's fixed
    setup (method/url/headers/timeout); *input_* is whatever the model
    decided to send this call (query_params/body).

    Raises on any failure — agent_llm_executor.run_agent_turn already catches
    exceptions from a tool executor and reports them to the model as a tool
    error, so this function does not need its own try/except-and-swallow.
    """
    validate_webhook_url(config["url"])  # re-validate at call time (DNS rebinding)

    url = config["url"]
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


def _validate_tool_config(tool_type: str, config: HttpToolConfig) -> None:
    if tool_type == "http_request":
        try:
            validate_webhook_url(config.url)
        except WebhookUrlError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
