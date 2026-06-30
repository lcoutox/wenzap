"""
Service for managing an agent's catalog scope (which categories it can access).

Scope model:
  - category_scope = "all"      → agent queries the entire workspace catalog.
  - category_scope = "selected" → agent queries only items in the linked categories.

When catalog_enabled=False the scope is preserved but ignored by retrieval.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.agent_catalog_category import AgentCatalogCategory
from app.models.catalog_category import CatalogCategory
from app.schemas.agent_catalog_scope import AgentCatalogScopeOut, AgentCatalogScopeUpdate


def get_catalog_scope(
    db: Session,
    *,
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> AgentCatalogScopeOut:
    """Return the current catalog scope for an agent."""
    agent = db.get(Agent, agent_id)
    if agent is None or agent.workspace_id != workspace_id:
        raise ValueError("Agent not found")

    rows = db.scalars(
        select(AgentCatalogCategory).where(
            AgentCatalogCategory.agent_id == agent_id,
            AgentCatalogCategory.workspace_id == workspace_id,
        )
    ).all()

    category_ids = [r.category_id for r in rows]
    category_scope = "selected" if category_ids else "all"

    return AgentCatalogScopeOut(
        catalog_enabled=agent.catalog_enabled,
        category_scope=category_scope,
        category_ids=category_ids,
    )


def update_catalog_scope(
    db: Session,
    *,
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    data: AgentCatalogScopeUpdate,
) -> AgentCatalogScopeOut:
    """
    Save catalog scope for an agent.

    - Validates all category_ids belong to workspace_id.
    - When scope is "all", clears all linked categories.
    - When scope is "selected", replaces linked categories with the provided list.
    - Always updates agent.catalog_enabled.
    """
    agent = db.get(Agent, agent_id)
    if agent is None or agent.workspace_id != workspace_id:
        raise ValueError("Agent not found")

    # Update catalog_enabled on the agent
    agent.catalog_enabled = data.catalog_enabled
    db.add(agent)

    # Resolve desired category IDs
    desired_ids: list[uuid.UUID] = []
    if data.category_scope == "selected" and data.category_ids:
        # Validate all IDs belong to this workspace
        valid_ids = set(
            db.scalars(
                select(CatalogCategory.id).where(
                    CatalogCategory.id.in_(data.category_ids),
                    CatalogCategory.workspace_id == workspace_id,
                )
            ).all()
        )
        desired_ids = [cid for cid in data.category_ids if cid in valid_ids]

    # Replace existing rows
    existing = db.scalars(
        select(AgentCatalogCategory).where(
            AgentCatalogCategory.agent_id == agent_id,
            AgentCatalogCategory.workspace_id == workspace_id,
        )
    ).all()
    existing_ids = {r.category_id: r for r in existing}

    desired_set = set(desired_ids)
    to_delete = [r for cid, r in existing_ids.items() if cid not in desired_set]
    to_add = [cid for cid in desired_ids if cid not in existing_ids]

    for row in to_delete:
        db.delete(row)
    for cid in to_add:
        db.add(AgentCatalogCategory(
            workspace_id=workspace_id,
            agent_id=agent_id,
            category_id=cid,
        ))

    db.commit()

    return AgentCatalogScopeOut(
        catalog_enabled=agent.catalog_enabled,
        category_scope="selected" if desired_ids else "all",
        category_ids=desired_ids,
    )


def get_allowed_category_ids(
    db: Session,
    *,
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> list[uuid.UUID] | None:
    """
    Return the list of allowed category IDs for catalog retrieval, or None if
    scope is "all" (no filtering needed).

    Called by the retrieval pipeline — fast path, single query.
    """
    rows = db.scalars(
        select(AgentCatalogCategory.category_id).where(
            AgentCatalogCategory.agent_id == agent_id,
            AgentCatalogCategory.workspace_id == workspace_id,
        )
    ).all()
    return list(rows) if rows else None
