"""
Tests for file_extractors: TxtExtractor, MarkdownExtractor, PdfExtractor,
CsvExtractor, and get_extractor factory.

PDF fixtures are raw minimal PDFs generated without external dependencies —
see tests/fixtures/sample_text.pdf and tests/fixtures/sample_no_text.pdf.
"""

import os

import pytest

from app.services.file_extractors import (
    CsvExtractor,
    ExtractionError,
    MarkdownExtractor,
    PdfExtractor,
    TxtExtractor,
    get_extractor,
)

# ── Fixtures path ─────────────────────────────────────────────────────────────

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name: str) -> bytes:
    with open(os.path.join(FIXTURES_DIR, name), "rb") as fh:
        return fh.read()


# ── TxtExtractor ──────────────────────────────────────────────────────────────

class TestTxtExtractor:
    def setup_method(self):
        self.extractor = TxtExtractor()

    def test_extracts_utf8_text(self):
        result = self.extractor.extract("Olá, mundo!".encode("utf-8"))
        assert "Olá, mundo!" in result

    def test_extracts_latin1_text(self):
        result = self.extractor.extract("Ação".encode("latin-1"))
        assert result.strip() != ""

    def test_empty_bytes_raises(self):
        with pytest.raises(ExtractionError, match="empty"):
            self.extractor.extract(b"")

    def test_whitespace_only_raises(self):
        with pytest.raises(ExtractionError, match="no usable text"):
            self.extractor.extract(b"   \n\t  ")

    def test_preserves_multiline_content(self):
        content = "Line 1\nLine 2\nLine 3"
        result = self.extractor.extract(content.encode("utf-8"))
        assert "Line 1" in result
        assert "Line 3" in result


# ── MarkdownExtractor ─────────────────────────────────────────────────────────

class TestMarkdownExtractor:
    def setup_method(self):
        self.extractor = MarkdownExtractor()

    def test_extracts_simple_markdown(self):
        md = b"# Title\n\nSome paragraph text.\n\n- item 1\n- item 2"
        result = self.extractor.extract(md)
        assert "Title" in result
        assert "Some paragraph text" in result

    def test_strips_frontmatter(self):
        md = b"---\ntitle: My Doc\ndate: 2024-01-01\n---\n\nReal content here."
        result = self.extractor.extract(md)
        assert "Real content here." in result
        assert "title: My Doc" not in result

    def test_frontmatter_only_raises(self):
        md = b"---\ntitle: Only frontmatter\n---\n"
        with pytest.raises(ExtractionError, match="no usable text"):
            self.extractor.extract(md)

    def test_empty_file_raises(self):
        with pytest.raises(ExtractionError, match="empty"):
            self.extractor.extract(b"")

    def test_whitespace_only_raises(self):
        with pytest.raises(ExtractionError, match="no usable text"):
            self.extractor.extract(b"\n\n   \n")

    def test_frontmatter_with_content_after_whitespace(self):
        md = b"---\nkey: value\n---\n\n\nActual content."
        result = self.extractor.extract(md)
        assert "Actual content." in result

    def test_no_frontmatter_works(self):
        md = b"# Just markdown\n\nNo frontmatter here."
        result = self.extractor.extract(md)
        assert "Just markdown" in result


# ── PdfExtractor ──────────────────────────────────────────────────────────────

class TestPdfExtractor:
    def setup_method(self):
        self.extractor = PdfExtractor()

    def test_extracts_text_from_pdf(self):
        data = _fixture("sample_text.pdf")
        result = self.extractor.extract(data)
        assert "Hello PDF" in result

    def test_rejects_file_without_pdf_magic_bytes(self):
        with pytest.raises(ExtractionError, match="%PDF"):
            self.extractor.extract(b"This is not a PDF at all")

    def test_empty_file_raises(self):
        with pytest.raises(ExtractionError, match="empty"):
            self.extractor.extract(b"")

    def test_invalid_pdf_structure_raises(self):
        # Starts with %PDF but is malformed/truncated
        with pytest.raises(ExtractionError):
            self.extractor.extract(b"%PDF-1.4 garbage data that is not a real PDF")

    def test_pdf_without_text_raises(self):
        data = _fixture("sample_no_text.pdf")
        with pytest.raises(ExtractionError, match="texto extraível"):
            self.extractor.extract(data)


# ── CsvExtractor ─────────────────────────────────────────────────────────────

class TestCsvExtractor:
    def setup_method(self):
        self.extractor = CsvExtractor()

    def test_extracts_csv_with_header(self):
        csv = b"Nome,Preco,Descricao\nProduto X,R$ 100,Teste\nProduto Y,R$ 200,Outro"
        result = self.extractor.extract(csv)
        assert "Linha 1:" in result
        assert "Nome: Produto X" in result
        assert "Linha 2:" in result
        assert "Nome: Produto Y" in result

    def test_format_includes_column_labels(self):
        csv = b"Coluna A,Coluna B\nval1,val2"
        result = self.extractor.extract(csv)
        assert "Coluna A: val1" in result
        assert "Coluna B: val2" in result

    def test_empty_cells_are_skipped(self):
        csv = b"Nome,Descricao\nProduto X,"
        result = self.extractor.extract(csv)
        assert "Nome: Produto X" in result
        # Empty Descricao must not appear
        assert "Descricao" not in result

    def test_empty_file_raises(self):
        with pytest.raises(ExtractionError, match="empty"):
            self.extractor.extract(b"")

    def test_whitespace_only_raises(self):
        with pytest.raises(ExtractionError, match="no usable content"):
            self.extractor.extract(b"   \n  ")

    def test_header_only_no_data_rows_raises(self):
        csv = b"Nome,Preco\n"
        with pytest.raises(ExtractionError, match="no data rows"):
            self.extractor.extract(csv)

    def test_all_rows_empty_cells_raises(self):
        csv = b"Nome,Preco\n,\n,"
        with pytest.raises(ExtractionError, match="no data rows"):
            self.extractor.extract(csv)

    def test_blank_header_names_rejected(self):
        # csv.DictReader with empty headers produces None or "" fieldnames
        csv = b",\nval1,val2"
        with pytest.raises(ExtractionError, match="no usable column names"):
            self.extractor.extract(csv)

    def test_row_limit_is_respected(self):
        # Generate CSV with 1100 rows; only first 1000 should be included
        header = "ID,Value\n"
        rows = "".join(f"{i},row{i}\n" for i in range(1, 1101))
        csv = (header + rows).encode("utf-8")
        result = self.extractor.extract(csv)
        assert "Linha 1000:" in result
        assert "Linha 1001:" not in result

    def test_latin1_csv(self):
        csv = "Nome,Descricao\nÁlvaro,Função especial".encode("latin-1")
        result = self.extractor.extract(csv)
        assert result.strip() != ""

    def test_multirow_format(self):
        csv = b"A,B\nv1,v2\nv3,v4"
        result = self.extractor.extract(csv)
        blocks = result.split("\n\n")
        assert len(blocks) == 2


# ── Factory ───────────────────────────────────────────────────────────────────

class TestGetExtractor:
    def test_txt_returns_txt_extractor(self):
        assert isinstance(get_extractor("txt"), TxtExtractor)

    def test_markdown_returns_markdown_extractor(self):
        assert isinstance(get_extractor("markdown"), MarkdownExtractor)

    def test_pdf_simple_returns_pdf_extractor(self):
        assert isinstance(get_extractor("pdf_simple"), PdfExtractor)

    def test_csv_simple_returns_csv_extractor(self):
        assert isinstance(get_extractor("csv_simple"), CsvExtractor)

    def test_unknown_type_raises_extraction_error(self):
        with pytest.raises(ExtractionError, match="No extractor available"):
            get_extractor("docx")

    def test_empty_type_raises_extraction_error(self):
        with pytest.raises(ExtractionError, match="No extractor available"):
            get_extractor("")

    def test_manual_text_raises_extraction_error(self):
        # manual_text and faq_qa are not file-based types
        with pytest.raises(ExtractionError):
            get_extractor("manual_text")
