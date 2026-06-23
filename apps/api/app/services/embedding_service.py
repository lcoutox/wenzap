"""
Embedding service — Phase 4.2.2.

Thin orchestration layer between callers (indexing service, retrieval) and
the concrete EmbeddingProvider. No DB access.
"""

from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider, EmbeddingResult


def embed_texts(
    texts: list[str],
    provider: EmbeddingProvider | None = None,
) -> EmbeddingResult:
    """
    Embed a list of texts using the given provider (or the configured default).

    Parameters
    ----------
    texts    : Strings to embed. Empty list returns an empty EmbeddingResult.
    provider : Optional provider override. If None, uses `get_embedding_provider()`.

    Returns
    -------
    EmbeddingResult with one embedding per input text.

    Raises
    ------
    EmbeddingError : On provider failure or if the result shape is unexpected.
    """
    if provider is None:
        from app.services.embedding_providers.factory import get_embedding_provider
        provider = get_embedding_provider()

    if not texts:
        return EmbeddingResult(
            embeddings=[],
            provider=provider.provider_name,
            model=provider.model,
            dimension=provider.dimension,
        )

    result = provider.embed(texts)

    # Validate quantity
    if len(result.embeddings) != len(texts):
        raise EmbeddingError(
            f"Provider returned {len(result.embeddings)} embeddings "
            f"for {len(texts)} texts."
        )

    # Validate each embedding's dimension
    expected_dim = provider.dimension
    for i, emb in enumerate(result.embeddings):
        if len(emb) != expected_dim:
            raise EmbeddingError(
                f"Embedding at index {i} has dimension {len(emb)}, "
                f"expected {expected_dim}."
            )

    return result
