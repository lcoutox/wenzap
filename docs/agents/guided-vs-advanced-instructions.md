# Agent Behavior UX.1 — Guided vs Advanced Instructions

## Overview

Agents in Nexbrain have two modes for configuring behavior instructions:

- **Guided mode** (`instructions_mode = "guided"`): structured form with pre-defined options for role, posture, initiative, do/don't lists, and examples. Recommended for most use cases.
- **Advanced mode** (`instructions_mode = "advanced"`): free-text field (`advanced_prompt`) for full control over the instructions sent to the LLM.

## Database

New columns added to `agent_prompt_settings` (migration `057`):

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `instructions_mode` | `VARCHAR(20) NOT NULL` | `'guided'` | `'guided'` or `'advanced'` |
| `guided_config` | `JSONB nullable` | `NULL` | Structured config (see schema below) |
| `advanced_prompt` | `TEXT nullable` | `NULL` | Free-text instructions for advanced mode |

Legacy columns (`system_prompt`, `persona`) are preserved. Data migration sets `instructions_mode = 'advanced'` for agents that had a non-empty `system_prompt`, copying the content into `advanced_prompt`.

## Guided config schema

```json
{
  "role": "customer_support | initial_support | consultive_sales | presales_qualification | relationship_postsale | reception_triage | custom | null",
  "main_objective": "string (max 500) | null",
  "posture": "consultive | direct | educational | welcoming | technical | null",
  "initiative": "only_respond | respond_suggest | drive_conversion | null",
  "when_no_info": "ask_context | direct_to_team | knowledge_only | null",
  "do_items": ["answer_company_questions", "explain_products", ...],
  "dont_items": ["no_fake_prices", "no_guarantee_results", ...],
  "extra_restrictions": "string (max 1000) | null",
  "good_response_example": "string (max 2000) | null",
  "bad_response_example": "string (max 2000) | null"
}
```

## Prompt assembly

`build_agent_instructions_block(settings)` in `agent_context_builder.py`:

1. If `instructions_mode == "advanced"`: uses `advanced_prompt`, falls back to legacy `system_prompt`.
2. If `instructions_mode == "guided"` and `guided_config` is set: calls `_compile_guided_config()` which assembles a structured English block.
3. If guided config is empty: falls back to legacy `system_prompt`.
4. Returns `None` if nothing is configured.

The resulting block is passed to `build_system_prompt()` as `agent_instructions_block`, where it is injected as `OPERATOR INSTRUCTIONS (follow strictly)`.

## Activation rules

- Advanced mode: `advanced_prompt` must be non-empty (or legacy `system_prompt` as fallback).
- Guided mode: either `guided_config` must have at least one field set, or legacy `system_prompt` must be non-empty.

## API

All fields are included in `PATCH /agents/{id}`:

```json
{
  "instructions_mode": "guided",
  "guided_config": { "role": "customer_support", "posture": "welcoming" },
  "advanced_prompt": null
}
```

Response (`AgentOut`) includes `instructions_mode`, `guided_config`, `advanced_prompt`.

## Frontend

`ConfigInstrucoes` component (tab "Instruções") replaces the old `ConfigPrompt`. It shows a mode toggle (Guiado / Avançado) and renders the appropriate form.
