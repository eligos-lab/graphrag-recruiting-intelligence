from collections.abc import Iterator
from pathlib import Path

from pypdf import PdfReader

from app.ingestion.schemas import DocumentType, SourceDocument
from app.ingestion.sources.base import BaseDataSource


class PdfResumeSource(BaseDataSource):
    def __init__(
        self,
        path: Path | str,
        source_name: str | None = None,
        *,
        max_file_size_mb: int = 25,
    ) -> None:
        super().__init__(path=path, source_name=source_name)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

    @property
    def source_type(self) -> str:
        return "pdf"

    def iter_documents(self) -> Iterator[SourceDocument]:
        file_size = self.path.stat().st_size
        if file_size > self.max_file_size_bytes:
            raise ValueError(
                f"PDF exceeds configured size limit ({file_size} > {self.max_file_size_bytes})"
            )
        reader = PdfReader(self.path)
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        raw_text = "\n\n".join(value for value in pages if value).strip()
        if not raw_text:
            raise ValueError("PDF contains no extractable text; OCR is required")
        yield SourceDocument(
            source=self.source_name,
            external_id=self.external_id({}, raw_text),
            document_type=DocumentType.PDF,
            raw_text=raw_text,
            payload={"text": raw_text},
            metadata={
                "filename": self.path.name,
                "page_count": len(reader.pages),
                "file_size_bytes": file_size,
            },
        )
