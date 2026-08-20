from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GraphNodeSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    normalized_name: str
    evidence_ids: list[UUID] = Field(default_factory=list)


class GraphCompanySnapshot(GraphNodeSnapshot):
    domains: list[GraphNodeSnapshot] = Field(default_factory=list)


class GraphProjectSnapshot(GraphNodeSnapshot):
    technologies: list[GraphNodeSnapshot] = Field(default_factory=list)
    domains: list[GraphNodeSnapshot] = Field(default_factory=list)


class PersonGraphSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    full_name: str
    country: str | None = None
    current_title: str | None = None
    evidence_ids: list[UUID] = Field(default_factory=list)
    companies: list[GraphCompanySnapshot] = Field(default_factory=list)
    skills: list[GraphNodeSnapshot] = Field(default_factory=list)
    technologies: list[GraphNodeSnapshot] = Field(default_factory=list)
    projects: list[GraphProjectSnapshot] = Field(default_factory=list)
    universities: list[GraphNodeSnapshot] = Field(default_factory=list)
    domains: list[GraphNodeSnapshot] = Field(default_factory=list)
