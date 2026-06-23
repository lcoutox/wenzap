from app.services.file_extractors.base import ExtractionError, FileExtractor


class TxtExtractor(FileExtractor):
    """Extract plain text from TXT files (UTF-8 with latin-1 fallback)."""

    def extract(self, data: bytes) -> str:
        if not data:
            raise ExtractionError("File is empty.")

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = data.decode("latin-1")
            except UnicodeDecodeError as exc:
                raise ExtractionError("File could not be decoded as UTF-8 or latin-1.") from exc

        if not text.strip():
            raise ExtractionError("File contains no usable text.")

        return text
