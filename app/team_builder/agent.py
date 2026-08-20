import re

from app.retrieval.hybrid import HybridRetriever
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import CandidateMatch
from app.team_builder.models import (
    TeamAssignment,
    TeamBuilderRequest,
    TeamBuildResponse,
    TeamRoleRequirement,
    UnfilledRole,
)

_WORD = re.compile(r"[a-z0-9+#.-]+", re.IGNORECASE)


class TeamBuilderAgent:
    def __init__(self, retriever: HybridRetriever) -> None:
        self.retriever = retriever

    async def build(self, request: TeamBuilderRequest) -> TeamBuildResponse:
        assignments: list[TeamAssignment] = []
        unfilled: list[UnfilledRole] = []
        selected_ids = set()
        selected_terms: set[str] = set()

        for requirement in request.roles:
            intent = self._intent(requirement, request.context)
            query = self._query(requirement, request.context)
            result = await self.retriever.search(
                query,
                intent,
                limit=request.candidates_per_role,
            )
            for slot in range(1, requirement.count + 1):
                available = [
                    candidate
                    for candidate in result.candidates
                    if candidate.candidate_id not in selected_ids
                ]
                if not available:
                    unfilled.append(
                        UnfilledRole(
                            role=requirement.role,
                            slot=slot,
                            reason="No remaining candidate satisfies the retrieval constraints",
                        )
                    )
                    continue
                candidate, selection_score = max(
                    (
                        (
                            item,
                            max(
                                0.0,
                                item.score
                                - request.diversity_weight
                                * self._overlap(self._terms(item), selected_terms),
                            ),
                        )
                        for item in available
                    ),
                    key=lambda pair: (pair[1], pair[0].score, str(pair[0].candidate_id)),
                )
                selected_ids.add(candidate.candidate_id)
                selected_terms.update(self._terms(candidate))
                assignments.append(
                    TeamAssignment(
                        role=requirement.role,
                        slot=slot,
                        candidate=candidate,
                        selection_score=selection_score,
                        rationale=candidate.reasons,
                    )
                )

        aggregate = (
            sum(item.selection_score for item in assignments) / len(assignments)
            if assignments
            else 0.0
        )
        return TeamBuildResponse(
            assignments=assignments,
            unfilled_roles=unfilled,
            aggregate_score=aggregate,
        )

    @staticmethod
    def _intent(
        requirement: TeamRoleRequirement,
        context: str | None,
    ) -> CandidateSearchIntent:
        return CandidateSearchIntent(
            role=requirement.role,
            seniority=requirement.seniority,
            location=requirement.location,
            min_years_experience=requirement.min_years_experience,
            required_skills=requirement.required_skills,
            required_technologies=requirement.required_technologies,
            required_domains=requirement.required_domains,
            preferred_skills=requirement.preferred_skills,
            preferred_domains=requirement.preferred_domains,
            semantic_query=context or requirement.role,
        )

    @staticmethod
    def _query(requirement: TeamRoleRequirement, context: str | None) -> str:
        details = [
            requirement.role,
            requirement.seniority or "",
            *requirement.required_skills,
            *requirement.required_technologies,
            *requirement.required_domains,
            context or "",
        ]
        return " ".join(value for value in details if value)

    @staticmethod
    def _terms(candidate: CandidateMatch) -> set[str]:
        return {
            word.casefold()
            for evidence in candidate.evidence
            for word in _WORD.findall(evidence.content)
            if len(word) > 2
        }

    @staticmethod
    def _overlap(terms: set[str], selected_terms: set[str]) -> float:
        union = terms | selected_terms
        return len(terms & selected_terms) / len(union) if union else 0.0
