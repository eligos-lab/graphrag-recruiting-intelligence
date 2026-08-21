from enum import StrEnum

from pydantic import BaseModel

from app.retrieval.intent import CandidateSearchIntent


class RetrievalOperation(StrEnum):
    STRUCTURED = "structured"
    VECTOR = "vector"
    GRAPH = "graph"


class QueryPlan(BaseModel):
    operations: list[RetrievalOperation]
    has_hard_filters: bool


class QueryPlanner:
    def plan(self, intent: CandidateSearchIntent) -> QueryPlan:
        has_hard_filters = bool(
            intent.location.country
            or intent.location.city
            or intent.location.cities
            or intent.min_years_experience is not None
            or intent.min_age is not None
            or intent.max_age is not None
            or intent.required_skills
            or intent.required_technologies
            or intent.required_domains
            or intent.companies
            or intent.projects
            or intent.unresolved_constraints
        )
        operations = [RetrievalOperation.STRUCTURED]
        if intent.semantic_query:
            operations.append(RetrievalOperation.VECTOR)
        if intent.required_domains or intent.companies or intent.projects:
            operations.append(RetrievalOperation.GRAPH)
        return QueryPlan(operations=operations, has_hard_filters=has_hard_filters)
