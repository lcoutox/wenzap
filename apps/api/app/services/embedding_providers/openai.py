from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider, EmbeddingResult


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding provider.

    Requires OPENAI_API_KEY to be set in settings (or the environment).
    Raises EmbeddingError at call-time (not import-time) if the key is missing.
    """

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
    ) -> None:
        if not api_key:
            raise EmbeddingError(
                "OPENAI_API_KEY is not set. "
                "Configure it in your .env file or set EMBEDDING_PROVIDER=mock for local dev."
            )
        self.api_key = api_key
        self.model = model
        self.dimension = dimension

    def embed(self, texts: list[str]) -> EmbeddingResult:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingError(
                "openai package is not installed. Run: uv add openai"
            ) from exc

        client = OpenAI(api_key=self.api_key)

        try:
            response = client.embeddings.create(
                input=texts,
                model=self.model,
                dimensions=self.dimension,
            )
        except Exception as exc:
            raise EmbeddingError(f"OpenAI embedding request failed: {exc}") from exc

        embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

        if len(embeddings) != len(texts):
            raise EmbeddingError(
                f"OpenAI returned {len(embeddings)} embeddings for {len(texts)} texts."
            )

        return EmbeddingResult(
            embeddings=embeddings,
            provider=self.provider_name,
            model=self.model,
            dimension=self.dimension,
        )
