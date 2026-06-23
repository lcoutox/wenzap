from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider


def get_embedding_provider() -> EmbeddingProvider:
    """
    Instantiate the configured embedding provider.

    Reads from `settings`:
    - EMBEDDING_PROVIDER  : "mock" | "openai"  (default: "mock")
    - EMBEDDING_MODEL     : provider model name (default: "text-embedding-3-small")
    - EMBEDDING_DIMENSION : vector dimension    (default: 1536)
    - OPENAI_API_KEY      : required when EMBEDDING_PROVIDER=openai

    Raises
    ------
    EmbeddingError : For unknown providers or missing configuration.
    """
    # Lazy import to avoid circular imports and to keep provider modules independent.
    from app.config import settings
    from app.services.embedding_providers.mock import MockEmbeddingProvider
    from app.services.embedding_providers.openai import OpenAIEmbeddingProvider

    provider_name = settings.embedding_provider.lower()

    if provider_name == "mock":
        return MockEmbeddingProvider(dimension=settings.embedding_dimension)

    if provider_name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )

    raise EmbeddingError(
        f"Unknown embedding provider: '{provider_name}'. "
        "Supported values: 'mock', 'openai'."
    )
