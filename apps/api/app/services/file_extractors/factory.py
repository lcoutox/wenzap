from app.services.file_extractors.base import ExtractionError, FileExtractor

_EXTRACTOR_MAP = {
    "txt": "app.services.file_extractors.txt_extractor.TxtExtractor",
    "markdown": "app.services.file_extractors.markdown_extractor.MarkdownExtractor",
    "pdf_simple": "app.services.file_extractors.pdf_extractor.PdfExtractor",
    "csv_simple": "app.services.file_extractors.csv_extractor.CsvExtractor",
}


def get_extractor(source_type: str) -> FileExtractor:
    """
    Return a FileExtractor for the given source_type.

    Raises ExtractionError for unknown source types.
    """
    qualified = _EXTRACTOR_MAP.get(source_type)
    if not qualified:
        supported = ", ".join(sorted(_EXTRACTOR_MAP))
        raise ExtractionError(
            f"No extractor available for source_type={source_type!r}. "
            f"Supported types: {supported}."
        )

    module_path, class_name = qualified.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()
