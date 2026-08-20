from enum import StrEnum

from pydantic import BaseModel, Field


class PersistOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    DUPLICATE = "duplicate"


class IngestionError(BaseModel):
    source: str
    external_id: str
    error_type: str
    message: str


class IngestionReport(BaseModel):
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[IngestionError] = Field(default_factory=list)
