from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Person:
    full_name: str
    source: str
    source_id: str
    id: UUID = field(default_factory=uuid4)
    location: str | None = None
    country: str | None = None
    current_title: str | None = None
    years_experience: float | None = None
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class Company:
    name: str
    id: UUID = field(default_factory=uuid4)
    industry: str | None = None
    country: str | None = None


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    normalized_name: str
    id: UUID = field(default_factory=uuid4)
    category: str | None = None


@dataclass(frozen=True, slots=True)
class Technology:
    name: str
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class Project:
    name: str
    id: UUID = field(default_factory=uuid4)
    description: str | None = None


@dataclass(frozen=True, slots=True)
class University:
    name: str
    id: UUID = field(default_factory=uuid4)
    country: str | None = None


@dataclass(frozen=True, slots=True)
class Domain:
    name: str
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True, slots=True)
class RawDocument:
    source: str
    external_id: str
    document_type: str
    raw_text: str
    checksum: str
    id: UUID = field(default_factory=uuid4)
    metadata: dict[str, object] = field(default_factory=dict)
