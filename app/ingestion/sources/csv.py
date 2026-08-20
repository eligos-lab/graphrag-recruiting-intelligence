import csv
from collections.abc import Iterator
from pathlib import Path

from app.ingestion.schemas import DocumentType, SourceDocument
from app.ingestion.sources.base import BaseDataSource


class CsvResumeSource(BaseDataSource):
    def __init__(
        self,
        path: Path | str,
        source_name: str | None = None,
        id_fields: tuple[str, ...] = ("external_id", "id", "email"),
        encoding: str = "utf-8-sig",
    ) -> None:
        super().__init__(path=path, source_name=source_name, id_fields=id_fields)
        self.encoding = encoding

    @property
    def source_type(self) -> str:
        return "csv"

    def iter_documents(self) -> Iterator[SourceDocument]:
        with self.path.open(encoding=self.encoding, newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError(f"CSV file has no header: {self.path}")

            for row_number, row in enumerate(reader, start=2):
                record = {key: value for key, value in row.items() if key is not None}
                raw_text = self.stable_raw_text(record)
                yield SourceDocument(
                    source=self.source_name,
                    external_id=self.external_id(record, raw_text),
                    document_type=DocumentType.CSV,
                    raw_text=raw_text,
                    payload=record,
                    metadata={"filename": self.path.name, "row_number": row_number},
                )
