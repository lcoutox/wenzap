import hashlib
import math

from app.services.embedding_providers.base import EmbeddingError, EmbeddingProvider, EmbeddingResult


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic mock provider for tests and local dev.

    Generates a stable embedding from the SHA-256 hash of each text so that:
    - Same text → same embedding (deterministic, repeatable).
    - Different texts → different embeddings (no collision for reasonable inputs).
    - The vector is L2-normalised to unit length (common expectation for cosine search).
    """

    provider_name = "mock"
    model = "mock-embedding"

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            raise EmbeddingError("embed() called with empty text list.")

        embeddings = [self._embed_one(t) for t in texts]
        return EmbeddingResult(
            embeddings=embeddings,
            provider=self.provider_name,
            model=self.model,
            dimension=self.dimension,
        )

    def _embed_one(self, text: str) -> list[float]:
        """
        Produce a deterministic unit-length vector from the text's SHA-256 digest.

        Strategy:
        1. Compute SHA-256(text) → 32 bytes.
        2. Seed a simple LCG using pairs of bytes to fill `dimension` floats.
        3. L2-normalise the vector.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()

        raw: list[float] = []
        seed = int.from_bytes(digest, "big")
        # LCG parameters (Numerical Recipes)
        a, c, m = 1664525, 1013904223, 2**32
        for _ in range(self.dimension):
            seed = (a * seed + c) % m
            # Map to [-1, 1]
            raw.append((seed / m) * 2.0 - 1.0)

        # L2 normalise
        magnitude = math.sqrt(sum(v * v for v in raw))
        if magnitude == 0.0:
            return [0.0] * self.dimension
        return [v / magnitude for v in raw]
