from io import BytesIO

from pypdf import PdfReader

from app.services.file_extractors.base import ExtractionError, FileExtractor

_PDF_MAGIC = b"%PDF"


class PdfExtractor(FileExtractor):
    """
    Extract plain text from PDF files using pypdf.

    Only PDFs with embedded text are supported. Scanned PDFs (image-only)
    will raise ExtractionError — OCR is out of scope.
    """

    def extract(self, data: bytes) -> str:
        if not data:
            raise ExtractionError("File is empty.")

        if not data.startswith(_PDF_MAGIC):
            raise ExtractionError("File does not appear to be a valid PDF (missing %PDF header).")

        try:
            reader = PdfReader(BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:
            raise ExtractionError(f"Failed to parse PDF: {exc}") from exc

        text = "\n\n".join(p for p in pages if p.strip())

        if not text.strip():
            raise ExtractionError(
                "PDF não contém texto extraível. Pode ser um PDF escaneado."
            )

        return text
