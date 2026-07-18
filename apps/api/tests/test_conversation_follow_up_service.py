"""
Unit tests for conversation_follow_up_service._build_follow_up_instruction —
follow-up-tool-prd.md adendo: combining the general (per-agent) instruction
with an optional per-step instruction, neither overriding the other.
"""

from app.services.conversation_follow_up_service import _build_follow_up_instruction


def test_instruction_with_neither_general_nor_step():
    text = _build_follow_up_instruction(
        hours_silent=6.4, step_number=1, total_steps=3,
        general_instructions=None, step_instructions=None,
    )
    assert "silêncio há aproximadamente 6 horas" in text
    assert "follow-up #1 de 3" in text
    assert "Instrução" not in text


def test_instruction_with_general_only():
    text = _build_follow_up_instruction(
        hours_silent=6, step_number=1, total_steps=3,
        general_instructions="Seja sempre gentil e nunca insista.",
        step_instructions=None,
    )
    assert "Instrução geral do operador" in text
    assert "Seja sempre gentil e nunca insista." in text
    assert "Instrução específica" not in text


def test_instruction_with_step_only():
    text = _build_follow_up_instruction(
        hours_silent=24, step_number=2, total_steps=3,
        general_instructions=None,
        step_instructions="Ofereça um cupom de 10% de desconto.",
    )
    assert "Instrução específica deste follow-up #2" in text
    assert "Ofereça um cupom de 10% de desconto." in text
    assert "Instrução geral" not in text


def test_instruction_with_both_general_and_step():
    text = _build_follow_up_instruction(
        hours_silent=72, step_number=3, total_steps=3,
        general_instructions="Mantenha o tom leve.",
        step_instructions="Avise que esse é o último contato antes de encerrar.",
    )
    assert "Instrução geral do operador" in text
    assert "Mantenha o tom leve." in text
    assert "Instrução específica deste follow-up #3" in text
    assert "Avise que esse é o último contato antes de encerrar." in text
