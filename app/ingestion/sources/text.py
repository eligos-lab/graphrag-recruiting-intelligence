from collections.abc import Iterator
from pathlib import Path

from app.ingestion.schemas import DocumentType, SourceDocument
from app.ingestion.sources.base import BaseDataSource


class TextResumeSource(BaseDataSource):
    def __init__(
        self,
        path: Path | str,
        source_name: str | None = None,
        encoding: str = "utf-8",
    ) -> None:
        super().__init__(path=path, source_name=source_name)
        self.encoding = encoding

    @property
    def source_type(self) -> str:
        return "text"

    def iter_documents(self) -> Iterator[SourceDocument]:
        raw_text = self.path.read_text(encoding=self.encoding).strip()
        if not raw_text:
            raise ValueError(f"Text resume is empty: {self.path}")
        yield SourceDocument(
            source=self.source_name,
            external_id=self.external_id({}, raw_text),
            document_type=DocumentType.TEXT,
            raw_text=raw_text,
            payload={"text": raw_text},
            metadata={"filename": self.path.name},
        )
