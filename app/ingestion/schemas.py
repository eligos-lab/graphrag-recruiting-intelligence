from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    CSV = "csv"
    JSON = "json"
    PDF = "pdf"
    TEXT = "text"


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    document_type: DocumentType
    raw_text: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperienceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1)
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    domains: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    university: str = Field(min_length=1)
    country: str | None = None
    degree: str | None = None
    field_of_study: str | None = None


class ProjectItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class CanonicalResume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    external_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    location: str | None = None
    country: str | None = None
    current_title: str | None = None
    years_experience: float | None = Field(default=None, ge=0)
    summary: str | None = None
    experience: list[ExperienceItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
