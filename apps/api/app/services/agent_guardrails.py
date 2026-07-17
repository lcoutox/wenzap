"""
Agent Guardrails — Phase 3.2.

Provides pattern-based prompt injection detection and a safe refusal message.

Scope (Phase 3.2):
  - Applied to customer/user messages in both the Playground and production
    Inbox replies.
  - Since the tool-calling PRD (Fase 5), also applied to tool_result content
    before it re-enters the model's context (app/services/agent_llm_executor.py)
    — a tool's output is untrusted data, same threat model as a user message.
  - Detection is regex-based (fast, no LLM call needed).
  - Covers the most common injection attempts in PT and EN.

Not in scope:
  - External moderation APIs
  - LLM-based risk classifiers
  - PII detection
  - RAG or public channel guardrails
"""

import re

# ── Injection patterns ────────────────────────────────────────────────────────
# Each pattern is matched case-insensitively against the full user message.
# Prefer specific multi-word patterns over short keywords to minimise false
# positives on legitimate messages that happen to contain common words.

_RAW_PATTERNS: list[str] = [
    # Override / ignore instructions — EN
    r"ignore previous instructions",
    r"ignore all previous instructions",
    r"ignore your instructions",
    r"disregard your instructions",
    r"disregard previous instructions",
    r"forget your instructions",
    r"forget previous instructions",
    r"override your instructions",
    r"override previous instructions",
    # Override / ignore instructions — PT
    r"ignore as instru[çc][õo]es anteriores",
    r"ignore suas instru[çc][õo]es",
    r"desconsidere suas instru[çc][õo]es",
    r"desconsidere as instru[çc][õo]es",
    r"esqueça suas instru[çc][õo]es",
    r"esqueça as instru[çc][õo]es",
    # Reveal system prompt — EN
    r"show your system prompt",
    r"reveal your system prompt",
    r"what is your system prompt",
    r"print your system prompt",
    r"repeat your system prompt",
    r"display your system prompt",
    r"output your system prompt",
    # Reveal system prompt — PT
    r"mostre seu prompt",
    r"mostre o seu prompt",
    r"revele seu prompt",
    r"revele o seu prompt",
    r"qual [ée] seu system prompt",
    r"qual [ée] o seu prompt",
    # Internal / developer messages — EN
    r"developer message",
    r"developer prompt",
    r"system message",
    r"internal instructions",
    # Internal / developer messages — PT
    r"mensagem de sistema",
    r"mensagem do sistema",
    r"instru[çc][õo]es internas",
    r"prompt do sistema",
    # Jailbreak keywords
    r"jailbreak",
    r"do anything now",
    r"\bdan\b",  # "DAN" — Do Anything Now
]

_COMPILED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in _RAW_PATTERNS
]

# ── Public API ────────────────────────────────────────────────────────────────

_SAFE_REFUSAL = (
    "Não posso ajudar com esse tipo de solicitação. "
    "Posso responder perguntas dentro do escopo deste agente."
)


def detect_prompt_injection(message: str) -> bool:
    """Return True if the message matches a known prompt injection pattern."""
    return any(pattern.search(message) for pattern in _COMPILED_PATTERNS)


def get_safe_refusal_message() -> str:
    """Return the standard safe refusal reply for detected injection attempts."""
    return _SAFE_REFUSAL
