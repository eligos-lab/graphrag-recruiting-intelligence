import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.ingestion.schemas import DocumentType, SourceDocument
from app.ingestion.sources.base import BaseDataSource


class JsonResumeSource(BaseDataSource):
    def __init__(
        self,
        path: Path | str,
        source_name: str | None = None,
        id_fields: tuple[str, ...] = ("external_id", "id", "email"),
        records_key: str = "records",
        encoding: str = "utf-8",
    ) -> None:
        super().__init__(path=path, source_name=source_name, id_fields=id_fields)
        self.records_key = records_key
        self.encoding = encoding

    @property
    def source_type(self) -> str:
        return "json"

    def iter_documents(self) -> Iterator[SourceDocument]:
        for record_number, record in enumerate(self._load_records(), start=1):
            raw_text = self.stable_raw_text(record)
            yield SourceDocument(
                source=self.source_name,
                external_id=self.external_id(record, raw_text),
                document_type=DocumentType.JSON,
                raw_text=raw_text,
                payload=record,
                metadata={"filename": self.path.name, "record_number": record_number},
            )

    def _load_records(self) -> list[dict[str, Any]]:
        if self.path.suffix.casefold() == ".jsonl":
            with self.path.open(encoding=self.encoding) as file:
                records = [json.loads(line) for line in file if line.strip()]
        else:
            with self.path.open(encoding=self.encoding) as file:
                payload = json.load(file)
            if isinstance(payload, list):
                records = payload
            elif isinstance(payload, dict) and isinstance(payload.get(self.records_key), list):
                records = payload[self.records_key]
            elif isinstance(payload, dict):
                records = [payload]
            else:
                raise ValueError(f"Unsupported JSON root in {self.path}")

        if not all(isinstance(record, dict) for record in records):
            raise ValueError(f"Every JSON record must be an object: {self.path}")
        return records
