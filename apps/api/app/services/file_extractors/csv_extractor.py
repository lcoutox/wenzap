import csv
import io

from app.services.file_extractors.base import ExtractionError, FileExtractor

_MAX_ROWS = 1000


class CsvExtractor(FileExtractor):
    """
    Extract readable text from CSV files with a header row.

    Each data row is rendered as a labelled block:

        Linha 1:
        Column A: value
        Column B: value

    Rules:
    - First row is treated as the header; blank or whitespace-only headers are rejected.
    - Empty cells are skipped.
    - At most MAX_ROWS data rows are processed (remaining rows are silently ignored).
    - If no data rows yield any content, ExtractionError is raised.
    """

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
            raise ExtractionError("File contains no usable content.")

        try:
            reader = csv.DictReader(io.StringIO(text))

            # Validate that header fields exist and are non-blank.
            if not reader.fieldnames:
                raise ExtractionError("CSV has no header row.")
            headers = [h for h in reader.fieldnames if h and h.strip()]
            if not headers:
                raise ExtractionError("CSV header row contains no usable column names.")

            lines: list[str] = []
            for row_num, row in enumerate(reader, start=1):
                if row_num > _MAX_ROWS:
                    break
                parts = [
                    f"{col}: {val}"
                    for col in headers
                    if (val := (row.get(col) or "").strip())
                ]
                if parts:
                    lines.append(f"Linha {row_num}:\n" + "\n".join(parts))

        except ExtractionError:
            raise
        except Exception as exc:
            raise ExtractionError(f"Failed to parse CSV: {exc}") from exc

        if not lines:
            raise ExtractionError("CSV contains no data rows with usable content.")

        return "\n\n".join(lines)
