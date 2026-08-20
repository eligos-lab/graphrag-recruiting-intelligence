import json
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.ingestion.schemas import SourceDocument


class BaseDataSource(ABC):
    def __init__(
        self,
        path: Path | str,
        source_name: str | None = None,
        id_fields: Sequence[str] = ("external_id", "id", "email"),
    ) -> None:
        self.path = Path(path)
        self.source_name = source_name or f"{self.source_type}:{self.path.name}"
        self.id_fields = tuple(id_fields)

    @property
    @abstractmethod
    def source_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def iter_documents(self) -> Iterator[SourceDocument]:
        raise NotImplementedError

    def stable_raw_text(self, record: Mapping[str, Any]) -> str:
        return json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)

    def external_id(self, record: Mapping[str, Any], raw_text: str) -> str:
        for field_name in self.id_fields:
            value = record.get(field_name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return f"checksum:{sha256(raw_text.encode('utf-8')).hexdigest()}"
