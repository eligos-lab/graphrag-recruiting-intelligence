from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceSource(StrEnum):
    STRUCTURED = "structured"
    VECTOR = "vector"
    GRAPH = "graph"


class ClaimKind(StrEnum):
    FACT = "fact"
    INFERENCE = "inference"


class CandidateEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: UUID
    chunk_id: UUID | None = None
    source: EvidenceSource
    content: str
    score: float = Field(ge=0, le=1)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: UUID
    full_name: str
    location: str | None = None
    country: str | None = None
    current_title: str | None = None
    years_experience: float | None = None
    age: int | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    semantic: float = Field(default=0, ge=0, le=1)
    skills: float = Field(default=0, ge=0, le=1)
    domains: float = Field(default=0, ge=0, le=1)
    experience: float = Field(default=0, ge=0, le=1)
    graph: float = Field(default=0, ge=0, le=1)
    location: float = Field(default=0, ge=0, le=1)
    preference: float = Field(default=0, ge=0, le=1)


class CandidateReason(BaseModel):
    claim: str
    kind: ClaimKind = ClaimKind.FACT
    evidence_ids: list[UUID] = Field(default_factory=list)
    confidence: float = Field(default=1, ge=0, le=1)


class CandidateMatch(BaseModel):
    candidate_id: UUID
    full_name: str
    current_title: str | None = None
    location: str | None = None
    years_experience: float | None = None
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=1)
    breakdown: ScoreBreakdown
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    reasons: list[CandidateReason] = Field(default_factory=list)


class GraphPath(BaseModel):
    person_id: UUID
    nodes: list[str]
    relationships: list[str]
    evidence_ids: list[UUID] = Field(default_factory=list)
    score: float = Field(default=0, ge=0, le=1)
