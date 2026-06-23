from abc import ABC, abstractmethod


class StorageError(Exception):
    """Raised for any storage-layer failure (I/O error, traversal attempt, etc.)."""


class StorageProvider(ABC):
    @abstractmethod
    def put_file(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Write *data* to *key*. Creates intermediate directories as needed."""

    @abstractmethod
    def get_file(self, key: str) -> bytes:
        """Return the raw bytes stored at *key*. Raises StorageError if not found."""

    @abstractmethod
    def delete_file(self, key: str) -> None:
        """Delete the file at *key*. No-op if the file does not exist."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if *key* exists in storage."""
