"""
Tests for voice_text_normalizer.normalize_for_speech —
whatsapp-voice-groq-elevenlabs-prd.md.

ElevenLabs' own normalizer mispronounces Brazilian-formatted numbers
(period as thousands separator, comma as decimal). This module rewrites
currency, measurements, dates, times, percentages, ordinals, and phone
numbers into spoken words before synthesis — covers more than just money
since Wenzap's clients span many niches (real estate, services, retail...).

Covers:
  - currency (with/without cents, round values, zero)
  - measurements (m², km, kg, °C, ha, ...) — singular vs plural
  - dates (with/without year, 2-digit year)
  - invalid "dates" (bad day/month) left untouched
  - times (on the hour, with minutes)
  - percentages (integer and decimal)
  - ordinals (1º, 3ª)
  - phone numbers (with/without DDI, parens, dash)
  - generic BR-formatted numbers without an explicit unit (fallback)
  - numbers WITHOUT separators are left untouched (already unambiguous)
  - combined multi-pattern text in one string
  - never raises — falls back to the original text on internal failure
"""

from unittest.mock import patch

from app.services.voice_text_normalizer import normalize_for_speech

# ── Currency ─────────────────────────────────────────────────────────────────


def test_currency_with_cents():
    assert (
        normalize_for_speech("Custa R$ 564.144,00.")
        == "Custa quinhentos e sessenta e quatro mil, cento e quarenta e quatro reais."
    )


def test_currency_with_nonzero_cents():
    result = normalize_for_speech("São R$ 1.500,50 por mês.")
    assert "mil e quinhentos reais e cinquenta centavos" in result


def test_currency_without_thousands_separator():
    assert normalize_for_speech("Custa R$ 50 apenas.") == "Custa cinquenta reais apenas."


def test_currency_zero():
    assert normalize_for_speech("Total: R$ 0,00.") == "Total: zero reais."


def test_currency_one_real_singular():
    assert "um real" in normalize_for_speech("Falta R$ 1,00.")


# ── Measurements ─────────────────────────────────────────────────────────────


def test_square_meters():
    assert (
        normalize_for_speech("O apartamento tem 120m².")
        == "O apartamento tem cento e vinte metros quadrados."
    )


def test_square_meters_singular():
    assert "um metro quadrado" in normalize_for_speech("Tem 1m² de sacada.")


def test_kilometers():
    assert normalize_for_speech("Fica a 3km da praia.") == "Fica a três quilômetros da praia."


def test_hectares_with_decimal():
    assert (
        normalize_for_speech("O terreno tem 2,5 hectares.")
        == "O terreno tem dois vírgula cinco hectares."
    )


def test_celsius():
    assert normalize_for_speech("Estão 22°C hoje.") == "Estão vinte e dois graus celsius hoje."


def test_kilograms():
    assert normalize_for_speech("Pesa 15kg.") == "Pesa quinze quilogramas."


def test_km_per_hour():
    assert "quilômetros por hora" in normalize_for_speech("Limite de 80km/h na via.")


def test_measurement_case_insensitive_unit():
    assert (
        normalize_for_speech("São 50Km de distância.")
        == "São cinquenta quilômetros de distância."
    )


def test_spelled_out_unit_is_left_alone():
    # Already words, not an abbreviation — no ambiguity to fix.
    assert (
        normalize_for_speech("A sala tem 25 metros quadrados de área.")
        == "A sala tem 25 metros quadrados de área."
    )


# ── Dates ────────────────────────────────────────────────────────────────────


def test_date_with_four_digit_year():
    assert (
        normalize_for_speech("Reunião em 20/07/2026.")
        == "Reunião em vinte de julho de dois mil e vinte e seis."
    )


def test_date_without_year():
    assert normalize_for_speech("Reunião dia 5/3.") == "Reunião dia cinco de março."


def test_date_with_two_digit_year():
    result = normalize_for_speech("Assinado em 01/01/26.")
    assert "dois mil e vinte e seis" in result


def test_invalid_date_left_untouched():
    # Month 99 and day 45 don't exist — must not crash or produce garbage.
    text = "Não é data: 45/99 não deveria quebrar."
    assert normalize_for_speech(text) == text


# ── Times ────────────────────────────────────────────────────────────────────


def test_time_on_the_hour():
    assert normalize_for_speech("Abre às 9:00.") == "Abre às nove horas."


def test_time_with_minutes():
    assert (
        normalize_for_speech("Podemos às 14:30?") == "Podemos às catorze horas e trinta minutos?"
    )


# ── Percentages ──────────────────────────────────────────────────────────────


def test_percent_integer():
    assert normalize_for_speech("Taxa de 100%.") == "Taxa de cem por cento."


def test_percent_decimal():
    assert (
        normalize_for_speech("Juros de 12,5% ao ano.")
        == "Juros de doze vírgula cinco por cento ao ano."
    )


# ── Ordinals ─────────────────────────────────────────────────────────────────


def test_ordinal_masculine_symbol():
    assert normalize_for_speech("Fica no 3º andar.") == "Fica no terceiro andar."


def test_ordinal_feminine_symbol():
    assert normalize_for_speech("É a 1ª opção.") == "É a primeira opção."


def test_ordinal_feminine_compound():
    assert normalize_for_speech("A 21ª unidade.") == "A vigésima primeira unidade."


# ── Phone numbers ────────────────────────────────────────────────────────────


def test_phone_with_parens_and_dash():
    assert (
        normalize_for_speech("Me liga no (11) 98765-4321.")
        == "Me liga no um um nove oito sete seis cinco quatro três dois um."
    )


def test_phone_with_country_code():
    result = normalize_for_speech("Whatsapp: 55 21 98888-7777.")
    assert result == "Whatsapp: cinco cinco dois um nove oito oito oito oito sete sete sete sete."


# ── Fallback (bare BR-formatted numbers) ─────────────────────────────────────


def test_fallback_thousands_separator_no_unit():
    assert (
        normalize_for_speech("Temos 1.500 clientes cadastrados.")
        == "Temos mil e quinhentos clientes cadastrados."
    )


def test_fallback_bare_decimal_comma():
    expected = "A nota foi oito vírgula cinco no teste."
    assert normalize_for_speech("A nota foi 8,5 no teste.") == expected


def test_plain_number_without_separator_is_untouched():
    # No ambiguity here — a normal TTS reads "2026" or "502" just fine already.
    assert normalize_for_speech("Sala 502, ano 2026.") == "Sala 502, ano 2026."


# ── Combined / integration ────────────────────────────────────────────────────


def test_combined_multiple_patterns_in_one_message():
    text = (
        "O apartamento de 120m² custa R$ 564.144,00, tem 12,5% de entrada e "
        "podemos visitar dia 20/07 às 14:30. Fica no 3º andar."
    )
    result = normalize_for_speech(text)
    assert "cento e vinte metros quadrados" in result
    assert "quinhentos e sessenta e quatro mil, cento e quarenta e quatro reais" in result
    assert "doze vírgula cinco por cento" in result
    assert "vinte de julho" in result
    assert "catorze horas e trinta minutos" in result
    assert "terceiro andar" in result
    assert "R$" not in result
    assert "%" not in result


def test_empty_string():
    assert normalize_for_speech("") == ""


def test_text_with_no_numbers_is_unchanged():
    text = "Sem números aqui, só texto normal."
    assert normalize_for_speech(text) == text


# ── Never raises ─────────────────────────────────────────────────────────────


def test_falls_back_to_original_text_on_internal_error():
    with patch(
        "app.services.voice_text_normalizer._parse_br_number", side_effect=Exception("boom")
    ):
        assert normalize_for_speech("R$ 100,00 qualquer coisa") == "R$ 100,00 qualquer coisa"
