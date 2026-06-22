# Technical Debt Register

Tracking known technical debt items with context, priority, and removal criteria.

**Format:** each item has a context section (why it was introduced), a removal criteria section (what must be true before removing), and a risk level.

---

## [TD-001] Legacy columns in `agents` table

**Status:** Active — introduced in Phase 2.4  
**Priority:** Medium  
**Target phase:** Phase 3.x or 4.x

### What it is

The following columns remain in `agents` for transition compatibility after Phase 2.4 moved them logically to satellite tables:

| Column | Satellite table | Satellite column |
|---|---|---|
| `agents.system_prompt` | `agent_prompt_settings` | `system_prompt` |
| `agents.persona` | `agent_prompt_settings` | `persona` |
| `agents.ai_model_id` | `agent_model_settings` | `ai_model_id` |
| `agents.model_name` | `agent_model_settings` | `model_name` |
| `agents.temperature` | `agent_model_settings` | `temperature` |

### Why it was kept

Phase 2.4 introduced a dual-write strategy: `agent_service.py` writes to both the satellite tables (primary source) and the legacy columns simultaneously. This allows a safe rollback to the pre-2.4 service without a migration downgrade.

See: `docs/architecture/AGENT_MODULE_ARCHITECTURE.md` — Phase 2.4 Implementation Notes.

### Criteria for removal

All of the following must be true before dropping these columns:

1. `agent_prompt_settings` and `agent_model_settings` have been live in production for at least one full deployment cycle with no data drift reported.
2. The dual-write has been validated: no inconsistency found between legacy columns and satellite records.
3. No code outside `agent_service.py` reads `agents.system_prompt`, `agents.persona`, `agents.ai_model_id`, `agents.model_name`, or `agents.temperature` directly.
4. All tests pass with satellite tables as the sole source (remove fallback in `_build_agent_out` and confirm tests still pass).
5. A migration downgrade plan exists and has been reviewed.

### How to remove

1. Grep the codebase for any direct access to the legacy columns outside `agent_service.py`.
2. Remove the fallback branches in `_build_agent_out` (lines `agent.system_prompt`, `agent.persona`, `agent.ai_model_id`, `agent.model_name`, `agent.temperature`).
3. Verify all 121+ tests still pass.
4. Create a new migration: `ALTER TABLE agents DROP COLUMN system_prompt, persona, ai_model_id, model_name, temperature`.
5. Remove dual-write code from `create_agent` and `update_agent` in `agent_service.py`.
6. Remove legacy columns from `Agent` SQLAlchemy model.
7. Update `docs/architecture/AGENT_MODULE_ARCHITECTURE.md` — "Estado atual" section.

**Risk if removed too early:** if service is rolled back without also rolling back the migration, all agent reads will return `null` for prompt/model fields.

---

## [TD-002] N+1 queries in `list_agents`

**Status:** Active — introduced in Phase 2.4  
**Priority:** Low (acceptable at current volume)  
**Target phase:** Before Phase 3 goes live with real users

### What it is

`list_agents` in `agent_service.py` issues one SELECT per agent for `agent_prompt_settings` and one for `agent_model_settings`. With N agents, this is 2N + 1 queries total.

### Why it was kept

Volume is negligible in MVP (< 10 agents per workspace). Premature optimization was avoided.

### Criteria for resolution

Resolve before `list_agents` is called with more than ~20 agents in production, or when profiling shows it as a latency bottleneck.

### How to fix

Replace the per-agent query loop with a single JOIN or use SQLAlchemy `selectinload`:

```python
# Option A: explicit JOIN
query = (
    select(Agent, AgentPromptSettings, AgentModelSettings)
    .outerjoin(AgentPromptSettings, AgentPromptSettings.agent_id == Agent.id)
    .outerjoin(AgentModelSettings, AgentModelSettings.agent_id == Agent.id)
    .where(Agent.workspace_id == workspace_id)
    .order_by(Agent.created_at.desc())
)

# Option B: selectinload (lazy-loads in one extra query each, not per-row)
query = (
    select(Agent)
    .options(selectinload(Agent.prompt_settings), selectinload(Agent.model_settings))
    .where(Agent.workspace_id == workspace_id)
)
```

Option B requires adding `relationship()` declarations to the `Agent` model.
