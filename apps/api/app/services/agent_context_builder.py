"""
Builds the final system prompt sent to the LLM for a given agent.

Phase 3 scope: identity + base system_prompt + persona only.
Future phases will extend this to include knowledge base context,
tool descriptions, and conversation memory.

The builder never receives or returns the user's message — it only
constructs the system turn. This keeps the signature stable across phases.
"""


def build_system_prompt(
    agent_name: str,
    agent_description: str | None,
    system_prompt: str,
    persona: str | None,
) -> str:
    """
    Compose the final system prompt to send to the LLM.

    Args:
        agent_name:        Name of the agent (used as identity anchor).
        agent_description: Optional description of the agent's purpose.
        system_prompt:     Core instructions from agent_prompt_settings.
        persona:           Optional tone/personality guidance.

    Returns:
        A single string ready to pass as the LLM system field.
    """
    parts: list[str] = []

    identity_lines = [f"You are {agent_name}."]
    if agent_description:
        identity_lines.append(agent_description)
    parts.append(" ".join(identity_lines))

    parts.append(system_prompt.strip())

    if persona and persona.strip():
        parts.append(f"Personality and tone: {persona.strip()}")

    return "\n\n".join(parts)
