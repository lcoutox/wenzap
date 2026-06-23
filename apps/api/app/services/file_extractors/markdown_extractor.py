import re

from app.services.file_extractors.base import ExtractionError, FileExtractor

# Matches a YAML frontmatter block at the very start of the document:
# --- (optional whitespace) \n ... \n --- (optional whitespace) \n
_FRONTMATTER_RE = re.compile(r"^\s*---\s*\n.*?\n---\s*\n", re.DOTALL)


class MarkdownExtractor(FileExtractor):
    """
    Extract text from Markdown files.

    Markdown is treated as plain text — no HTML rendering or AST parsing.
    YAML frontmatter (--- ... ---) at the start of the file is stripped.
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

        # Strip YAML frontmatter if present.
        text = _FRONTMATTER_RE.sub("", text, count=1)

        if not text.strip():
            raise ExtractionError("File contains no usable text after removing frontmatter.")

        return text
