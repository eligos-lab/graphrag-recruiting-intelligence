from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.intent import LocationIntent
from app.retrieval.models import CandidateMatch, CandidateReason


class TeamRoleRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=2, max_length=255)
    count: int = Field(default=1, ge=1, le=10)
    seniority: str | None = None
    location: LocationIntent = Field(default_factory=LocationIntent)
    min_years_experience: float | None = Field(default=None, ge=0)
    required_skills: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)


class TeamBuilderRequest(BaseModel):
    roles: list[TeamRoleRequirement] = Field(min_length=1, max_length=20)
    context: str | None = Field(default=None, max_length=2_000)
    candidates_per_role: int = Field(default=20, ge=1, le=100)
    diversity_weight: float = Field(default=0.15, ge=0, le=0.5)


class TeamAssignment(BaseModel):
    role: str
    slot: int
    candidate: CandidateMatch
    selection_score: float = Field(ge=0, le=1)
    rationale: list[CandidateReason] = Field(default_factory=list)


class UnfilledRole(BaseModel):
    role: str
    slot: int
    reason: str


class TeamBuildResponse(BaseModel):
    assignments: list[TeamAssignment]
    unfilled_roles: list[UnfilledRole]
    aggregate_score: float = Field(ge=0, le=1)
