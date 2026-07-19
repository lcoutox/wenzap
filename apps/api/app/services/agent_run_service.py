"""
Agent Run Service — execucoes-log-prd.md.

Read-only service backing the "Auditoria" dashboard screen and the Inbox
error indicator. Reuses data already collected by conversation_agent_reply_service
(ConversationAgentRun) and agent_llm_executor (AgentToolCall) — this module
adds no new write paths, only queries.
"""

import uuid
from datetime import datetime

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_tool_call import AgentToolCall
from app.models.contact import Contact
from app.models.conversation import Conversation
from app.models.conversation_agent_run import ConversationAgentRun

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


def _run_to_dict(
    run: ConversationAgentRun,
    contact_name: str | None,
    contact_phone: str | None,
    agent_name: str | None,
    tool_names: list[str],
) -> dict:
    return {
        "id": str(run.id),
        "conversation_id": str(run.conversation_id),
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "agent_id": str(run.agent_id),
        "agent_name": agent_name,
        "status": run.status,
        "had_tool_error": run.had_tool_error,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "credits_used": run.credits_used,
        "duration_ms": run.duration_ms,
        "tool_names": tool_names,
        "created_at": run.created_at.isoformat(),
    }


def _attach_tool_names(db: Session, runs: list[ConversationAgentRun]) -> dict[uuid.UUID, list[str]]:
    """Bulk-fetch tool names used per run — one IN query, not N+1."""
    run_ids = [r.id for r in runs]
    if not run_ids:
        return {}
    rows = db.execute(
        select(AgentToolCall.conversation_agent_run_id, AgentToolCall.tool_calls).where(
            AgentToolCall.conversation_agent_run_id.in_(run_ids)
        )
    ).all()
    out: dict[uuid.UUID, list[str]] = {}
    for run_id, tool_calls in rows:
        seen = out.setdefault(run_id, [])
        for tc in tool_calls or []:
            name = tc.get("tool_name")
            if name and name not in seen:
                seen.append(name)
    return out


def list_agent_runs(
    db: Session,
    workspace_id: uuid.UUID,
    *,
    status_filter: str | None = None,
    had_error: bool = False,
    agent_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    tool_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = 0,
    limit: int = _DEFAULT_LIMIT,
) -> list[dict]:
    """
    List agent runs for the workspace, newest first.

    had_error=True is a convenience filter: any real failure, whether the
    whole turn crashed (status="failed") or completed with a failed tool
    call inside it (had_tool_error=True) — the two are otherwise orthogonal.
    """
    effective_limit = min(limit, _MAX_LIMIT)
    q = (
        select(
            ConversationAgentRun,
            Contact.name.label("contact_name"),
            Contact.phone.label("contact_phone"),
            Agent.name.label("agent_name"),
        )
        .join(Conversation, ConversationAgentRun.conversation_id == Conversation.id)
        .outerjoin(Contact, Conversation.contact_id == Contact.id)
        .outerjoin(Agent, ConversationAgentRun.agent_id == Agent.id)
        .where(ConversationAgentRun.workspace_id == workspace_id)
    )

    if status_filter is not None:
        q = q.where(ConversationAgentRun.status == status_filter)
    if had_error:
        q = q.where(
            (ConversationAgentRun.status == "failed")
            | (ConversationAgentRun.had_tool_error.is_(True))
        )
    if agent_id is not None:
        q = q.where(ConversationAgentRun.agent_id == agent_id)
    if conversation_id is not None:
        q = q.where(ConversationAgentRun.conversation_id == conversation_id)
    if date_from is not None:
        q = q.where(ConversationAgentRun.created_at >= date_from)
    if date_to is not None:
        q = q.where(ConversationAgentRun.created_at <= date_to)
    if tool_name:
        # JSONB containment: does some element of tool_calls have this
        # tool_name, regardless of its other keys (input/output/status)?
        tool_filter = cast([{"tool_name": tool_name}], JSONB)
        subq = select(AgentToolCall.id).where(
            AgentToolCall.conversation_agent_run_id == ConversationAgentRun.id,
            AgentToolCall.tool_calls.op("@>")(tool_filter),
        )
        q = q.where(subq.exists())

    q = q.order_by(ConversationAgentRun.created_at.desc()).offset(skip).limit(effective_limit)

    rows = db.execute(q).all()
    runs = [row[0] for row in rows]
    tool_names_by_run = _attach_tool_names(db, runs)

    return [
        _run_to_dict(
            run, contact_name, contact_phone, agent_name, tool_names_by_run.get(run.id, [])
        )
        for run, contact_name, contact_phone, agent_name in rows
    ]


def get_agent_run_detail(db: Session, workspace_id: uuid.UUID, run_id: uuid.UUID) -> dict | None:
    """Full detail for one run: the run itself + every tool call inside it, flattened."""
    row = db.execute(
        select(
            ConversationAgentRun,
            Contact.name.label("contact_name"),
            Contact.phone.label("contact_phone"),
            Agent.name.label("agent_name"),
        )
        .join(Conversation, ConversationAgentRun.conversation_id == Conversation.id)
        .outerjoin(Contact, Conversation.contact_id == Contact.id)
        .outerjoin(Agent, ConversationAgentRun.agent_id == Agent.id)
        .where(
            ConversationAgentRun.id == run_id,
            ConversationAgentRun.workspace_id == workspace_id,
        )
    ).first()
    if row is None:
        return None
    run, contact_name, contact_phone, agent_name = row

    call_rows = db.scalars(
        select(AgentToolCall)
        .where(AgentToolCall.conversation_agent_run_id == run_id)
        .order_by(AgentToolCall.call_index)
    ).all()

    tool_calls: list[dict] = []
    for call in call_rows:
        for tc in call.tool_calls or []:
            tool_calls.append({
                "call_index": call.call_index,
                "tool_name": tc.get("tool_name"),
                "input": tc.get("input"),
                "output": tc.get("output"),
                "status": tc.get("status"),
            })

    out = _run_to_dict(
        run, contact_name, contact_phone, agent_name,
        [tc["tool_name"] for tc in tool_calls if tc["tool_name"]],
    )
    out["tool_calls"] = tool_calls
    return out
