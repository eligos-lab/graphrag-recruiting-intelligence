from pathlib import Path

import pytest
from pypdf import PdfWriter

from app.ingestion.sources import PdfResumeSource


def test_pdf_source_rejects_image_only_or_empty_pdf_with_ocr_message(tmp_path: Path) -> None:
    path = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as file:
        writer.write(file)

    with pytest.raises(ValueError, match="OCR"):
        list(PdfResumeSource(path).iter_documents())
