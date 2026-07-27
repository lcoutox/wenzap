"""
Voice text normalizer — whatsapp-voice-groq-elevenlabs-prd.md.

Rewrites numbers, currency, measurements, dates, times, percentages,
ordinals, and phone numbers into spoken Portuguese words BEFORE the text is
sent to ElevenLabs for synthesis.

Why: ElevenLabs' own text normalizer struggles with Brazilian-formatted
numbers — period as thousands separator, comma as decimal (the inverse of
English convention) — and reads "R$ 564.144,00" digit-by-digit or garbled
instead of "quinhentos e sessenta e quatro mil, cento e quarenta e quatro
reais". Confirmed against ElevenLabs' own docs, which recommend exactly this:
pre-processing the text with regex before sending it to synthesis. Since
Wenzap serves clients across many niches (real estate, services, retail...),
this covers currency, generic measurements (m², km, kg, °C, ...), dates,
times, percentages, ordinals (1º andar), and phone numbers — not just money.

Only applied to the text SENT TO SYNTHESIS. Never touches the text message
shown in the chat bubble, which stays in its normal, readable format.

Never raises — normalization is best-effort; any unexpected failure falls
back to the original, unnormalized text rather than breaking the voice
reply entirely.
"""

import logging
import re

from num2words import num2words

logger = logging.getLogger(__name__)

_LANG = "pt_BR"

_DIGIT_WORDS = {
    "0": "zero", "1": "um", "2": "dois", "3": "três", "4": "quatro",
    "5": "cinco", "6": "seis", "7": "sete", "8": "oito", "9": "nove",
}

_MONTHS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

# unit token (lowercase, as it appears in text) -> (singular, plural) spoken form.
# Ordered by insertion below from longest/most-specific to shortest so the
# regex alternation (built from this dict) tries "km²" before "km" before "m".
_UNITS = {
    "km²": ("quilômetro quadrado", "quilômetros quadrados"),
    "km2": ("quilômetro quadrado", "quilômetros quadrados"),
    "m²": ("metro quadrado", "metros quadrados"),
    "m2": ("metro quadrado", "metros quadrados"),
    "km/h": ("quilômetro por hora", "quilômetros por hora"),
    "m/s": ("metro por segundo", "metros por segundo"),
    "°c": ("grau celsius", "graus celsius"),
    "ha": ("hectare", "hectares"),
    "km": ("quilômetro", "quilômetros"),
    "cm": ("centímetro", "centímetros"),
    "mm": ("milímetro", "milímetros"),
    "kg": ("quilograma", "quilogramas"),
    "ton": ("tonelada", "toneladas"),
    "ml": ("mililitro", "mililitros"),
    "m": ("metro", "metros"),
    "g": ("grama", "gramas"),
    "l": ("litro", "litros"),
}

_BR_NUMBER = r"\d{1,3}(?:\.\d{3})*(?:,\d+)?"

_PHONE_RE = re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b")
_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_CURRENCY_RE = re.compile(rf"R\$\s?({_BR_NUMBER})")
_PERCENT_RE = re.compile(rf"({_BR_NUMBER})\s?%")
_UNIT_ALTERNATION = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
_UNIT_RE = re.compile(rf"({_BR_NUMBER})\s?({_UNIT_ALTERNATION})\b", re.IGNORECASE)
_ORDINAL_RE = re.compile(r"\b(\d{1,3})[ºª°]")
# Fallback: any remaining BR-formatted number NOT already consumed above —
# requires a "." thousands group and/or a "," decimal, i.e. the specific
# ambiguous formatting that trips up the TTS normalizer. Plain digit runs
# without separators (e.g. "2026", "502") are left alone — those already
# read fine.
_FALLBACK_RE = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+")


def _parse_br_number(raw: str) -> float:
    return float(raw.replace(".", "").replace(",", "."))


def _number_words(value: float) -> str:
    if value == int(value):
        return num2words(int(value), lang=_LANG)
    return num2words(value, lang=_LANG)


def _phone_to_words(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return " ".join(_DIGIT_WORDS[d] for d in digits)


def _date_to_words(match: re.Match) -> str:
    day_raw, month_raw, year_raw = match.group(1), match.group(2), match.group(3)
    day, month = int(day_raw), int(month_raw)
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return match.group(0)

    day_words = num2words(day, lang=_LANG)
    month_name = _MONTHS[month - 1]
    if year_raw is None:
        return f"{day_words} de {month_name}"

    year = int(year_raw)
    if year < 100:
        year += 2000
    return f"{day_words} de {month_name} de {num2words(year, lang=_LANG)}"


def _time_to_words(match: re.Match) -> str:
    hour, minute = int(match.group(1)), int(match.group(2))
    hour_words = num2words(hour, lang=_LANG)
    if minute == 0:
        return f"{hour_words} horas"
    return f"{hour_words} horas e {num2words(minute, lang=_LANG)} minutos"


def _currency_to_words(match: re.Match) -> str:
    value = _parse_br_number(match.group(1))
    return num2words(value, lang=_LANG, to="currency")


def _percent_to_words(match: re.Match) -> str:
    value = _parse_br_number(match.group(1))
    return f"{_number_words(value)} por cento"


def _measurement_to_words(match: re.Match) -> str:
    value = _parse_br_number(match.group(1))
    singular, plural = _UNITS[match.group(2).lower()]
    unit_name = singular if value == 1 else plural
    return f"{_number_words(value)} {unit_name}"


def _ordinal_to_words(match: re.Match) -> str:
    words = num2words(int(match.group(1)), lang=_LANG, to="ordinal")
    if match.group(0)[-1] == "ª":
        # "ª" marks a feminine ordinal (e.g. "1ª opção") — num2words only
        # returns the masculine form, so flip trailing "o"s to "a" across the
        # whole phrase (handles compounds like "vigésimo primeiro").
        words = re.sub(r"o\b", "a", words)
    return words


def _fallback_to_words(match: re.Match) -> str:
    return _number_words(_parse_br_number(match.group(0)))


def normalize_for_speech(text: str) -> str:
    """
    Rewrite numbers/currency/measurements/dates/times/percentages/ordinals/
    phone numbers into spoken words. Falls back to the original text on any
    unexpected error — normalization must never break a voice reply.
    """
    try:
        result = text
        result = _PHONE_RE.sub(_phone_to_words, result)
        result = _DATE_RE.sub(_date_to_words, result)
        result = _TIME_RE.sub(_time_to_words, result)
        result = _CURRENCY_RE.sub(_currency_to_words, result)
        result = _PERCENT_RE.sub(_percent_to_words, result)
        result = _UNIT_RE.sub(_measurement_to_words, result)
        result = _ORDINAL_RE.sub(_ordinal_to_words, result)
        result = _FALLBACK_RE.sub(_fallback_to_words, result)
        return result
    except Exception:
        logger.exception("voice_text_normalizer failed, falling back to raw text")
        return text
