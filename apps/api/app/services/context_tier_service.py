"""
Context Tier Service — Agent Model UX.1.

Centralises context tier configuration: labels, character budgets, credit
multipliers, per-component limits, and plan availability matrix.

Design:
- Tiers define a shared character budget, not separate per-component limits.
  We allocate the budget to components in priority order:
    1. Safety/identity (fixed, always reserved).
    2. Agent instructions + response style (agent config).
    3. RAG context (dynamic, highest value).
    4. Catalog context (dynamic).
    5. Conversation history (oldest turns dropped first).
- Credit cost = model.credits_per_message * credit_multiplier.
- Plan gating is enforced at PATCH time (agent_service) and at read time
  (AiCatalogOut already shows available=True/False per model).
"""

from typing import Literal

ContextTier = Literal["economical", "standard", "broad", "advanced", "maximum"]

_VALID_TIERS: frozenset[str] = frozenset(
    ["economical", "standard", "broad", "advanced", "maximum"]
)

# Per-tier configuration. All character budgets are approximate — actual prompt
# size depends on agent config length. Components scale proportionally.
CONTEXT_TIER_CONFIG: dict[str, dict] = {
    "economical": {
        "label":             "Econômico",
        "description":       "Menor custo. Ideal para conversas simples e respostas rápidas.",
        "max_chars":         6_000,
        "credit_multiplier": 1,
        # Per-component limits derived from the overall budget
        "history_limit":     5,
        "rag_max_chars":     3_000,
        "catalog_limit":     1,
    },
    "standard": {
        "label":             "Padrão",
        "description":       "Recomendado para a maioria dos agentes. Equilibra custo e contexto.",
        "max_chars":         15_000,
        "credit_multiplier": 2,
        "history_limit":     20,
        "rag_max_chars":     8_000,
        "catalog_limit":     3,
    },
    "broad": {
        "label":             "Amplo",
        "description":       "Considera mais histórico e informações conectadas.",
        "max_chars":         25_000,
        "credit_multiplier": 4,
        "history_limit":     40,
        "rag_max_chars":     12_000,
        "catalog_limit":     5,
    },
    "advanced": {
        "label":             "Avançado",
        "description":       "Indicado para conversas longas e atendimentos mais complexos.",
        "max_chars":         35_000,
        "credit_multiplier": 8,
        "history_limit":     60,
        "rag_max_chars":     18_000,
        "catalog_limit":     8,
    },
    "maximum": {
        "label":             "Máximo",
        "description":       "Maior contexto disponível. Alto consumo de créditos.",
        "max_chars":         300_000,
        "credit_multiplier": 16,
        "history_limit":     500,
        "rag_max_chars":     150_000,
        "catalog_limit":     20,
    },
}

# Which tiers each plan can use.
# Tiers not listed for a plan are blocked at API level.
CONTEXT_TIER_PLAN_MATRIX: dict[str, frozenset[str]] = {
    "starter":    frozenset(["economical", "standard"]),
    "growth":     frozenset(["economical", "standard", "broad", "advanced"]),
    "scale":      frozenset(["economical", "standard", "broad", "advanced", "maximum"]),
    "enterprise": frozenset(["economical", "standard", "broad", "advanced", "maximum"]),
}

_DEFAULT_TIER: ContextTier = "standard"


def get_tier_config(tier: str) -> dict:
    """Return config dict for *tier*, falling back to standard if unknown."""
    return CONTEXT_TIER_CONFIG.get(tier, CONTEXT_TIER_CONFIG[_DEFAULT_TIER])


def plan_allows_context_tier(plan_code: str, tier: str) -> bool:
    """Return True when *plan_code* is allowed to use *tier*."""
    allowed = CONTEXT_TIER_PLAN_MATRIX.get(plan_code, CONTEXT_TIER_PLAN_MATRIX["starter"])
    return tier in allowed


def validate_context_tier(tier: str) -> bool:
    """Return True when *tier* is a valid tier code."""
    return tier in _VALID_TIERS


def calculate_credits(base_credits: int, tier: str) -> int:
    """Return credits consumed for one response at *tier*."""
    multiplier = get_tier_config(tier).get("credit_multiplier", 2)
    return max(1, base_credits * multiplier)
