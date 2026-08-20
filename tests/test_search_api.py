from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_search_service
from app.main import create_app
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import CandidateMatch, ScoreBreakdown
from app.retrieval.planner import RetrievalOperation
from app.services.search import SearchExecutionResult, SearchTimings


class FakeSearchService:
    async def search(
        self,
        query: str,
        *,
        limit: int,
        generate_answer: bool,
    ) -> SearchExecutionResult:
        return SearchExecutionResult(
            parsed_intent=CandidateSearchIntent(role="backend engineer"),
            candidates=[
                CandidateMatch(
                    candidate_id=uuid4(),
                    full_name="Ada Lovelace",
                    score=0.9,
                    breakdown=ScoreBreakdown(skills=1),
                )
            ],
            retrieval_strategy=[RetrievalOperation.STRUCTURED],
            timings=SearchTimings(total_ms=1.5),
        )


async def test_search_endpoint_returns_intent_scores_strategy_and_latency() -> None:
    application = create_app()
    application.dependency_overrides[get_search_service] = lambda: FakeSearchService()
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/search",
            json={"query": "Find a backend engineer", "limit": 10},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["parsed_intent"]["role"] == "backend engineer"
    assert payload["candidates"][0]["breakdown"]["skills"] == 1
    assert payload["retrieval_strategy"] == ["structured"]
    assert payload["timings"]["total_ms"] == 1.5
