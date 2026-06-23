"""Unit tests for chunking_service — Phase 4.2.2."""

import pytest

from app.services.chunking_service import (
    chunk_faq_qa,
    chunk_source_content,
    chunk_text,
    normalize_text,
)

# ── normalize_text ────────────────────────────────────────────────────────────


def test_normalize_tabs_to_spaces():
    assert normalize_text("hello\tworld") == "hello world"


def test_normalize_multiple_spaces():
    assert normalize_text("a  b   c") == "a b c"


def test_normalize_strips_edges():
    assert normalize_text("  hello  ") == "hello"


def test_normalize_preserves_paragraph_breaks():
    text = "First paragraph.\n\nSecond paragraph."
    result = normalize_text(text)
    assert "First paragraph." in result
    assert "Second paragraph." in result
    assert "\n\n" in result


def test_normalize_collapses_excessive_newlines():
    result = normalize_text("a\n\n\n\nb")
    assert result == "a\n\nb"


def test_normalize_strips_trailing_spaces_from_lines():
    result = normalize_text("hello   \nworld")
    assert result == "hello\nworld"


def test_normalize_empty_string():
    assert normalize_text("") == ""


def test_normalize_only_whitespace():
    assert normalize_text("   \t\t  ") == ""


# ── chunk_text ────────────────────────────────────────────────────────────────


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_chunk_text_whitespace_only():
    assert chunk_text("   \n  ") == []


def test_chunk_text_small_fits_single_chunk():
    text = "Short text that fits in one chunk."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].char_count == len(chunks[0].content)


def test_chunk_text_large_produces_multiple_chunks():
    # 9 000 chars > default chunk_size of 3 000
    text = "A" * 9000
    chunks = chunk_text(text)
    assert len(chunks) > 1


def test_chunk_text_chunk_index_sequential():
    text = "word " * 1000  # ~5 000 chars
    chunks = chunk_text(text)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_chunk_text_char_count_matches_content():
    text = "Hello world! " * 400
    chunks = chunk_text(text)
    for chunk in chunks:
        assert chunk.char_count == len(chunk.content)


def test_chunk_text_overlap_carries_content():
    # With chunk_size=3000, overlap=400, step=2600:
    # chunk 0: chars 0-3000, chunk 1: 2600-5600, chunk 2: 5200-6000 (800 chars)
    # All three are above min_chunk_chars=50.
    text = "x" * 6000
    chunks = chunk_text(text, chunk_size_chars=3000, overlap_chars=400)
    assert len(chunks) == 3
    # The overlap means chunk 1 starts 400 chars before where chunk 0 ended
    assert chunks[1].content.startswith("x")


def test_chunk_text_no_empty_chunks():
    text = "a" * 10000
    chunks = chunk_text(text, chunk_size_chars=100, overlap_chars=10, min_chunk_chars=5)
    for chunk in chunks:
        assert chunk.content.strip() != ""
        assert chunk.char_count > 0


def test_chunk_text_overlap_gte_chunk_size_raises():
    with pytest.raises(ValueError, match="overlap_chars"):
        chunk_text("some text", chunk_size_chars=100, overlap_chars=100)


def test_chunk_text_overlap_gt_chunk_size_raises():
    with pytest.raises(ValueError, match="overlap_chars"):
        chunk_text("some text", chunk_size_chars=100, overlap_chars=150)


def test_chunk_text_tiny_text_below_min_returns_single_chunk():
    # Text is shorter than chunk_size — should return it as one chunk even if < min_chunk_chars
    text = "Hi"
    chunks = chunk_text(text, min_chunk_chars=50)
    assert len(chunks) == 1
    assert chunks[0].content == "Hi"


def test_chunk_text_custom_sizes():
    text = "ab" * 500  # 1 000 chars
    chunks = chunk_text(text, chunk_size_chars=200, overlap_chars=20, min_chunk_chars=10)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= 200


# ── chunk_faq_qa ─────────────────────────────────────────────────────────────


def test_chunk_faq_single_pair():
    pairs = [{"question": "What is X?", "answer": "X is Y."}]
    chunks = chunk_faq_qa(pairs)
    assert len(chunks) == 1
    assert "Pergunta: What is X?" in chunks[0].content
    assert "Resposta: X is Y." in chunks[0].content


def test_chunk_faq_multiple_pairs():
    pairs = [
        {"question": "Q1", "answer": "A1"},
        {"question": "Q2", "answer": "A2"},
        {"question": "Q3", "answer": "A3"},
    ]
    chunks = chunk_faq_qa(pairs)
    assert len(chunks) == 3


def test_chunk_faq_index_sequential():
    pairs = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(5)]
    chunks = chunk_faq_qa(pairs)
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


def test_chunk_faq_metadata_contains_qa_index_and_question():
    pairs = [{"question": "Hello?", "answer": "World."}]
    chunks = chunk_faq_qa(pairs)
    assert chunks[0].metadata is not None
    assert chunks[0].metadata["source_type"] == "faq_qa"
    assert chunks[0].metadata["qa_index"] == 0
    assert chunks[0].metadata["question"] == "Hello?"


def test_chunk_faq_skips_empty_pairs():
    pairs = [
        {"question": "", "answer": ""},
        {"question": "Valid?", "answer": "Yes."},
        {"question": "NoAnswer", "answer": ""},
    ]
    chunks = chunk_faq_qa(pairs)
    # Only "Valid?" / "Yes." should produce a chunk
    assert len(chunks) == 1
    assert "Valid?" in chunks[0].content


def test_chunk_faq_skips_missing_keys():
    pairs = [
        {"question": "Only question"},  # no "answer" key
        {"question": "Full?", "answer": "Full!"},
    ]
    chunks = chunk_faq_qa(pairs)
    assert len(chunks) == 1
    assert "Full?" in chunks[0].content


def test_chunk_faq_qa_index_in_metadata_reflects_original_position():
    # Pair at position 0 is invalid and skipped; pair at position 1 is valid.
    # The valid chunk's qa_index should be 1 (original position), not 0.
    pairs = [
        {"question": "", "answer": ""},
        {"question": "Real?", "answer": "Real."},
    ]
    chunks = chunk_faq_qa(pairs)
    assert len(chunks) == 1
    assert chunks[0].metadata["qa_index"] == 1


def test_chunk_faq_char_count_correct():
    pairs = [{"question": "Q", "answer": "A"}]
    chunks = chunk_faq_qa(pairs)
    assert chunks[0].char_count == len(chunks[0].content)


# ── chunk_source_content (dispatcher) ────────────────────────────────────────


def test_chunk_source_content_manual_text():
    chunks = chunk_source_content(
        source_type="manual_text",
        content_text="Hello world",
        metadata_json=None,
    )
    assert len(chunks) == 1
    assert "Hello" in chunks[0].content


def test_chunk_source_content_faq_qa_uses_pairs():
    metadata = {
        "qa_pairs": [
            {
                "question": "What is Nexbrain?",
                "answer": "An AI agent orchestration platform for business operations.",
            },
        ]
    }
    # Use min_chunk_chars=20 because chunk_source_content defaults to 50 and the
    # generated "Pergunta: …\nResposta: …" must exceed that threshold.
    chunks = chunk_source_content(
        source_type="faq_qa",
        content_text=None,
        metadata_json=metadata,
        min_chunk_chars=20,
    )
    assert len(chunks) == 1
    assert "What is Nexbrain?" in chunks[0].content
    assert chunks[0].metadata["source_type"] == "faq_qa"


def test_chunk_source_content_faq_fallback_to_content_text():
    # qa_pairs missing → fall back to content_text
    chunks = chunk_source_content(
        source_type="faq_qa",
        content_text="Fallback text here",
        metadata_json={},
    )
    assert len(chunks) == 1
    assert "Fallback" in chunks[0].content


def test_chunk_source_content_empty_content_returns_empty():
    chunks = chunk_source_content(
        source_type="manual_text",
        content_text="",
        metadata_json=None,
    )
    assert chunks == []


def test_chunk_source_content_none_content_returns_empty():
    chunks = chunk_source_content(
        source_type="manual_text",
        content_text=None,
        metadata_json=None,
    )
    assert chunks == []


def test_chunk_source_content_unknown_type_falls_back_to_text():
    chunks = chunk_source_content(
        source_type="url",  # not yet implemented — defaults to text
        content_text="Some scraped content",
        metadata_json=None,
    )
    assert len(chunks) == 1
