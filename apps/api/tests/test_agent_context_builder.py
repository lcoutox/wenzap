"""
Tests for build_agent_instructions_block and _compile_guided_config.
"""

from app.services.agent_context_builder import (
    _compile_guided_config,
    build_agent_instructions_block,
)


# ── _compile_guided_config ────────────────────────────────────────────────────

def test_compile_empty_config_returns_none():
    assert _compile_guided_config({}) is None


def test_compile_role_only():
    result = _compile_guided_config({"role": "initial_support"})
    assert result is not None
    assert "Role:" in result
    assert "receive visitors" in result


def test_compile_custom_role_no_role_text():
    # "custom" role has no canned text — skipped
    result = _compile_guided_config({"role": "custom", "main_objective": "Be helpful"})
    assert result is not None
    assert "Main objective:" in result


def test_compile_main_objective():
    result = _compile_guided_config({"main_objective": "Help users find products"})
    assert "Main objective:" in result
    assert "Help users find products" in result


def test_compile_posture():
    result = _compile_guided_config({"posture": "direct"})
    assert "Conversation posture:" in result
    assert "direct" in result.lower()


def test_compile_initiative():
    result = _compile_guided_config({"initiative": "drive_conversion"})
    assert "Initiative level:" in result
    assert "qualification" in result


def test_compile_do_items():
    result = _compile_guided_config({"do_items": ["answer_company_questions", "qualify_leads"]})
    assert "What you should do:" in result
    assert "Answer questions about the company." in result
    assert "Qualify interested visitors" in result


def test_compile_dont_items():
    result = _compile_guided_config({"dont_items": ["no_fake_prices", "no_guarantee_results"]})
    assert "What you must not do:" in result
    assert "Do not invent prices" in result
    assert "Do not guarantee results." in result


def test_compile_extra_restrictions():
    result = _compile_guided_config({"extra_restrictions": "Never mention competitor names"})
    assert "Never mention competitor names" in result


def test_compile_when_no_info():
    result = _compile_guided_config({"when_no_info": "direct_to_team"})
    assert "When information is missing:" in result
    assert "connect the visitor with the team" in result


def test_compile_good_and_bad_examples():
    result = _compile_guided_config({
        "good_response_example": "Sure! Let me explain...",
        "bad_response_example": "I don't know, sorry.",
    })
    assert "Example of a good response:" in result
    assert "Sure! Let me explain..." in result
    assert "Response to avoid:" in result
    assert "I don't know, sorry." in result


def test_compile_unknown_do_item_skipped():
    result = _compile_guided_config({"do_items": ["unknown_item"]})
    # Should produce no do section (only header part)
    assert result is None or "What you should do:" not in (result or "")


# ── build_agent_instructions_block ────────────────────────────────────────────

class _FakeSettings:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_advanced_mode_returns_advanced_prompt():
    s = _FakeSettings(
        instructions_mode="advanced",
        advanced_prompt="You are an expert sales agent.",
        system_prompt=None,
        guided_config=None,
    )
    result = build_agent_instructions_block(s)
    assert result == "You are an expert sales agent."


def test_advanced_mode_falls_back_to_system_prompt():
    s = _FakeSettings(
        instructions_mode="advanced",
        advanced_prompt=None,
        system_prompt="Legacy prompt here.",
        guided_config=None,
    )
    result = build_agent_instructions_block(s)
    assert result == "Legacy prompt here."


def test_advanced_mode_empty_returns_none():
    s = _FakeSettings(
        instructions_mode="advanced",
        advanced_prompt="   ",
        system_prompt="",
        guided_config=None,
    )
    assert build_agent_instructions_block(s) is None


def test_guided_mode_with_config():
    s = _FakeSettings(
        instructions_mode="guided",
        advanced_prompt=None,
        system_prompt=None,
        guided_config={"role": "customer_support", "posture": "welcoming"},
    )
    result = build_agent_instructions_block(s)
    assert result is not None
    assert "Agent behavior instructions:" in result
    assert "customer" in result.lower()


def test_guided_mode_empty_config_falls_back_to_system_prompt():
    s = _FakeSettings(
        instructions_mode="guided",
        advanced_prompt=None,
        system_prompt="Old school prompt",
        guided_config={},
    )
    result = build_agent_instructions_block(s)
    assert result == "Old school prompt"


def test_guided_mode_none_config_falls_back_to_system_prompt():
    s = _FakeSettings(
        instructions_mode="guided",
        advanced_prompt=None,
        system_prompt="Old school prompt",
        guided_config=None,
    )
    result = build_agent_instructions_block(s)
    assert result == "Old school prompt"


def test_guided_mode_empty_config_no_system_prompt_returns_none():
    s = _FakeSettings(
        instructions_mode="guided",
        advanced_prompt=None,
        system_prompt=None,
        guided_config=None,
    )
    assert build_agent_instructions_block(s) is None


def test_no_instructions_mode_defaults_to_guided_with_fallback():
    s = _FakeSettings(
        system_prompt="Fallback prompt",
        guided_config=None,
        advanced_prompt=None,
    )
    # No instructions_mode attr at all
    result = build_agent_instructions_block(s)
    assert result == "Fallback prompt"
