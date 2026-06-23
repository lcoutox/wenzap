from abc import ABC, abstractmethod
from dataclasses import dataclass


class EmbeddingError(Exception):
    """Raised when an embedding operation fails (provider error, config error, etc.)."""


@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]
    provider: str
    model: str
    dimension: int


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    provider_name: str
    model: str
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResult:
        """
        Embed a batch of texts.

        Parameters
        ----------
        texts : Non-empty list of strings to embed.

        Returns
        -------
        EmbeddingResult with one embedding per input text.

        Raises
        ------
        EmbeddingError : On any provider-side failure.
        """
