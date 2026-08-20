from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IngestionJobOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generate_embeddings: bool = True
    update_graph: bool = True


class IngestionJobRequest(IngestionJobOptions):
    path: str = Field(min_length=1, max_length=1_024)
    source_name: str | None = Field(default=None, max_length=255)


class IngestionJob(BaseModel):
    id: UUID
    status: IngestionJobStatus
    path: str
    source_name: str | None = None
    options: IngestionJobOptions
    celery_task_id: str | None = None
    report: dict[str, Any] | None = None
    error: str | None = None


class IngestionBatch(BaseModel):
    jobs: list[IngestionJob]
    skipped_files: list[str] = Field(default_factory=list)


SUPPORTED_INGESTION_SUFFIXES = frozenset({".csv", ".json", ".jsonl", ".pdf", ".txt", ".md"})


def resolve_ingestion_path(data_root: Path, relative_path: str) -> Path:
    root = data_root.resolve()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Ingestion path must stay inside the configured data root")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate
