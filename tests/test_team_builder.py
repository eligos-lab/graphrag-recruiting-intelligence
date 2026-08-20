from typing import cast
from uuid import uuid4

from app.retrieval.hybrid import HybridRetrievalResult, HybridRetriever
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import CandidateMatch, ScoreBreakdown
from app.team_builder.agent import TeamBuilderAgent
from app.team_builder.models import TeamBuilderRequest, TeamRoleRequirement


class FakeHybridRetriever:
    def __init__(self, by_role: dict[str, list[CandidateMatch]]) -> None:
        self.by_role = by_role

    async def search(
        self,
        query: str,
        intent: CandidateSearchIntent,
        *,
        limit: int,
    ) -> HybridRetrievalResult:
        return HybridRetrievalResult(
            candidates=self.by_role.get(intent.role or "", [])[:limit],
            strategy=[],
        )


def match(name: str, score: float) -> CandidateMatch:
    return CandidateMatch(
        candidate_id=uuid4(),
        full_name=name,
        score=score,
        breakdown=ScoreBreakdown(),
    )


async def test_team_builder_selects_unique_candidates_and_reports_unfilled_slots() -> None:
    ada = match("Ada", 0.95)
    grace = match("Grace", 0.85)
    linus = match("Linus", 0.90)
    retriever = FakeHybridRetriever(
        {
            "backend engineer": [ada, grace],
            "platform engineer": [ada, linus],
        }
    )
    agent = TeamBuilderAgent(cast(HybridRetriever, retriever))

    result = await agent.build(
        TeamBuilderRequest(
            roles=[
                TeamRoleRequirement(role="backend engineer", count=2),
                TeamRoleRequirement(role="platform engineer", count=2),
            ]
        )
    )

    selected_ids = [assignment.candidate.candidate_id for assignment in result.assignments]
    assert selected_ids == [ada.candidate_id, grace.candidate_id, linus.candidate_id]
    assert len(set(selected_ids)) == len(selected_ids)
    assert result.unfilled_roles[0].role == "platform engineer"
    assert result.unfilled_roles[0].slot == 2
