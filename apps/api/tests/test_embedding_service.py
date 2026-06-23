"""Unit tests for embedding_service and embedding_providers — Phase 4.2.2.

No real network calls are made in any test.
"""

import math

import pytest

from app.services.embedding_providers.base import EmbeddingError, EmbeddingResult
from app.services.embedding_providers.factory import get_embedding_provider
from app.services.embedding_providers.mock import MockEmbeddingProvider
from app.services.embedding_providers.openai import OpenAIEmbeddingProvider
from app.services.embedding_service import embed_texts

# ── MockEmbeddingProvider ─────────────────────────────────────────────────────


def test_mock_returns_correct_dimension():
    provider = MockEmbeddingProvider(dimension=128)
    result = provider.embed(["hello"])
    assert len(result.embeddings[0]) == 128


def test_mock_default_dimension_is_1536():
    provider = MockEmbeddingProvider()
    result = provider.embed(["hello"])
    assert len(result.embeddings[0]) == 1536


def test_mock_is_deterministic():
    provider = MockEmbeddingProvider(dimension=64)
    r1 = provider.embed(["same text"])
    r2 = provider.embed(["same text"])
    assert r1.embeddings[0] == r2.embeddings[0]


def test_mock_different_texts_produce_different_embeddings():
    provider = MockEmbeddingProvider(dimension=64)
    r1 = provider.embed(["hello"])
    r2 = provider.embed(["world"])
    assert r1.embeddings[0] != r2.embeddings[0]


def test_mock_multiple_texts_returns_one_per_text():
    provider = MockEmbeddingProvider(dimension=64)
    texts = ["a", "b", "c"]
    result = provider.embed(texts)
    assert len(result.embeddings) == 3


def test_mock_vector_is_unit_length():
    provider = MockEmbeddingProvider(dimension=128)
    result = provider.embed(["normalise me"])
    vec = result.embeddings[0]
    magnitude = math.sqrt(sum(v * v for v in vec))
    assert abs(magnitude - 1.0) < 1e-6


def test_mock_provider_name_and_model():
    provider = MockEmbeddingProvider()
    assert provider.provider_name == "mock"
    assert provider.model == "mock-embedding"


def test_mock_empty_text_list_raises():
    provider = MockEmbeddingProvider()
    with pytest.raises(EmbeddingError):
        provider.embed([])


def test_mock_result_reports_correct_metadata():
    provider = MockEmbeddingProvider(dimension=32)
    result = provider.embed(["x"])
    assert result.provider == "mock"
    assert result.model == "mock-embedding"
    assert result.dimension == 32


# ── OpenAIEmbeddingProvider ───────────────────────────────────────────────────


def test_openai_raises_embedding_error_without_api_key():
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider(api_key="")


def test_openai_raises_embedding_error_with_none_key():
    with pytest.raises(EmbeddingError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider(api_key=None)  # type: ignore[arg-type]


def test_openai_no_network_call_on_instantiation():
    # If a key is provided, __init__ should succeed without hitting the network.
    provider = OpenAIEmbeddingProvider(api_key="sk-fake-key-for-test")
    assert provider.provider_name == "openai"
    assert provider.model == "text-embedding-3-small"
    assert provider.dimension == 1536


# ── Factory ───────────────────────────────────────────────────────────────────


def test_factory_returns_mock_by_default(monkeypatch):
    monkeypatch.setattr("app.config.settings.embedding_provider", "mock")
    provider = get_embedding_provider()
    assert isinstance(provider, MockEmbeddingProvider)


def test_factory_returns_mock_explicitly(monkeypatch):
    monkeypatch.setattr("app.config.settings.embedding_provider", "mock")
    provider = get_embedding_provider()
    assert provider.provider_name == "mock"


def test_factory_openai_without_key_raises(monkeypatch):
    monkeypatch.setattr("app.config.settings.embedding_provider", "openai")
    monkeypatch.setattr("app.config.settings.openai_api_key", "")
    with pytest.raises(EmbeddingError):
        get_embedding_provider()


def test_factory_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr("app.config.settings.embedding_provider", "cohere")
    with pytest.raises(EmbeddingError, match="Unknown embedding provider"):
        get_embedding_provider()


# ── embed_texts ───────────────────────────────────────────────────────────────


def test_embed_texts_empty_list_returns_empty_result():
    provider = MockEmbeddingProvider(dimension=64)
    result = embed_texts([], provider=provider)
    assert result.embeddings == []
    assert result.provider == "mock"
    assert result.dimension == 64


def test_embed_texts_returns_one_per_text():
    provider = MockEmbeddingProvider(dimension=64)
    result = embed_texts(["a", "b", "c"], provider=provider)
    assert len(result.embeddings) == 3


def test_embed_texts_validates_quantity_mismatch(monkeypatch):
    """If the provider returns wrong count, embed_texts should raise."""
    provider = MockEmbeddingProvider(dimension=4)

    # Patch embed to return fewer embeddings than requested
    original_embed = provider.embed

    def bad_embed(texts: list[str]) -> EmbeddingResult:
        result = original_embed(texts)
        result.embeddings = result.embeddings[:1]  # truncate
        return result

    monkeypatch.setattr(provider, "embed", bad_embed)

    with pytest.raises(EmbeddingError, match="embeddings"):
        embed_texts(["a", "b", "c"], provider=provider)


def test_embed_texts_validates_dimension_mismatch(monkeypatch):
    """If an embedding has the wrong dimension, embed_texts should raise."""
    provider = MockEmbeddingProvider(dimension=4)

    original_embed = provider.embed

    def bad_embed(texts: list[str]) -> EmbeddingResult:
        result = original_embed(texts)
        result.embeddings = [[1.0, 2.0]]  # only 2 floats instead of 4
        return result

    monkeypatch.setattr(provider, "embed", bad_embed)

    with pytest.raises(EmbeddingError, match="dimension"):
        embed_texts(["a"], provider=provider)


def test_embed_texts_uses_default_provider(monkeypatch):
    """embed_texts() with no provider arg should use get_embedding_provider()."""
    monkeypatch.setattr("app.config.settings.embedding_provider", "mock")
    monkeypatch.setattr("app.config.settings.embedding_dimension", 64)
    result = embed_texts(["hello"])
    assert result.provider == "mock"
    assert len(result.embeddings) == 1
    assert len(result.embeddings[0]) == 64
