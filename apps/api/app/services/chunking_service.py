"""
Chunking service — Phase 4.2.2.

Pure functions: no DB access, no external calls, fully unit-testable.

Entry point for the rest of the system is `chunk_source_content`, which dispatches
by source_type and returns an ordered list of ChunkData ready for indexing.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkData:
    content: str
    chunk_index: int
    char_count: int
    metadata: dict[str, Any] | None = field(default=None)


# ── Normalisation ─────────────────────────────────────────────────────────────

def normalize_text(text: str) -> str:
    """Normalise whitespace while preserving paragraph structure."""
    # Tabs → single space
    text = text.replace("\t", " ")
    # Collapse runs of spaces (but not newlines) to a single space
    text = re.sub(r" {2,}", " ", text)
    # Collapse runs of 3+ newlines to exactly two (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace from each line
    lines = [line.rstrip(" ") for line in text.split("\n")]
    text = "\n".join(lines)
    return text.strip()


# ── Text chunking (character-based with overlap) ──────────────────────────────

def chunk_text(
    text: str,
    chunk_size_chars: int = 3000,
    overlap_chars: int = 400,
    min_chunk_chars: int = 50,
) -> list[ChunkData]:
    """
    Split *text* into overlapping character-window chunks.

    Parameters
    ----------
    text            : Already-normalised input string.
    chunk_size_chars: Maximum characters per chunk (default 3000).
    overlap_chars   : Characters carried over from the previous chunk (default 400).
    min_chunk_chars : Chunks shorter than this are dropped, unless it is the only chunk
                      produced and the source text is shorter than chunk_size_chars.

    Raises
    ------
    ValueError  : If overlap_chars >= chunk_size_chars (would cause infinite loop).
    """
    if overlap_chars >= chunk_size_chars:
        raise ValueError(
            f"overlap_chars ({overlap_chars}) must be less than "
            f"chunk_size_chars ({chunk_size_chars})."
        )

    text = normalize_text(text)
    if not text:
        return []

    # If the entire text fits in one chunk, return it even if < min_chunk_chars.
    if len(text) <= chunk_size_chars:
        return [ChunkData(content=text, chunk_index=0, char_count=len(text))]

    chunks: list[ChunkData] = []
    start = 0
    step = chunk_size_chars - overlap_chars

    while start < len(text):
        end = start + chunk_size_chars
        chunk_content = text[start:end].strip()

        if chunk_content and len(chunk_content) >= min_chunk_chars:
            chunks.append(
                ChunkData(
                    content=chunk_content,
                    chunk_index=len(chunks),
                    char_count=len(chunk_content),
                )
            )

        start += step

    return chunks


# ── FAQ / Q&A chunking ────────────────────────────────────────────────────────

def chunk_faq_qa(
    qa_pairs: list[dict[str, str]],
    min_chunk_chars: int = 20,
) -> list[ChunkData]:
    """
    Convert a list of Q&A dicts into one ChunkData per valid pair.

    Each chunk's metadata contains:
      - source_type: "faq_qa"
      - qa_index: position in the original list (0-based)
      - question: the original question text

    Pairs where both question and answer are blank after strip are silently skipped.
    Partial pairs (only question or only answer) are also skipped.
    """
    chunks: list[ChunkData] = []

    for i, pair in enumerate(qa_pairs):
        question = (pair.get("question") or "").strip()
        answer = (pair.get("answer") or "").strip()

        if not question or not answer:
            continue

        content = f"Pergunta: {question}\nResposta: {answer}"

        if len(content) < min_chunk_chars:
            continue

        chunks.append(
            ChunkData(
                content=content,
                chunk_index=len(chunks),
                char_count=len(content),
                metadata={
                    "source_type": "faq_qa",
                    "qa_index": i,
                    "question": question,
                },
            )
        )

    return chunks


# ── Dispatcher ────────────────────────────────────────────────────────────────

def chunk_source_content(
    source_type: str,
    content_text: str | None,
    metadata_json: dict[str, Any] | None,
    chunk_size_chars: int = 3000,
    overlap_chars: int = 400,
    min_chunk_chars: int = 50,
) -> list[ChunkData]:
    """
    Top-level dispatcher: choose chunking strategy based on source_type.

    Returns an ordered list of ChunkData (may be empty if source has no content).
    Does not raise on missing/empty content — that validation belongs to the
    indexing service that calls this function.
    """
    if source_type == "faq_qa":
        qa_pairs: list[dict[str, str]] | None = None
        if metadata_json:
            raw = metadata_json.get("qa_pairs")
            if isinstance(raw, list) and raw:
                qa_pairs = raw

        if qa_pairs:
            # For faq_qa, pair validity is non-empty question + answer.
            # Character length is not a meaningful filter for Q&A chunks,
            # so we always use min_chunk_chars=1 here.
            return chunk_faq_qa(qa_pairs, min_chunk_chars=1)

        # Fallback: chunk content_text like manual_text
        return chunk_text(
            content_text or "",
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
            min_chunk_chars=min_chunk_chars,
        )

    # Default path: manual_text and any unrecognised source_type
    return chunk_text(
        content_text or "",
        chunk_size_chars=chunk_size_chars,
        overlap_chars=overlap_chars,
        min_chunk_chars=min_chunk_chars,
    )
