from abc import ABC, abstractmethod


class ExtractionError(Exception):
    """Raised when a file cannot be parsed or yields no usable text."""


class FileExtractor(ABC):
    @abstractmethod
    def extract(self, data: bytes) -> str:
        """
        Extract plain text from *data*.

        Returns a non-empty string on success.
        Raises ExtractionError if the file is empty, unreadable, or yields no text.
        """
