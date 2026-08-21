from collections.abc import Sequence
from uuid import UUID, uuid4

from app.ranking.scoring import CompositeRanker
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import CandidateEvidence, CandidateProfile, EvidenceSource, GraphPath
from app.retrieval.planner import RetrievalOperation
from app.services.embeddings import EmbeddingService


class FakeEmbeddingProvider:
    model = "test-embedding"
    dimension = 2

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class FakeStructuredRepository:
    def __init__(self, ids: set[UUID], profiles: dict[UUID, CandidateProfile]) -> None:
        self.ids = ids
        self._profiles = profiles

    async def filter_ids(self, intent: CandidateSearchIntent, *, limit: int) -> set[UUID]:
        return set(list(self.ids)[:limit])

    async def profiles(self, person_ids: set[UUID]) -> dict[UUID, CandidateProfile]:
        return {key: value for key, value in self._profiles.items() if key in person_ids}

    async def evidence(self, person_ids: set[UUID]) -> dict[UUID, list[CandidateEvidence]]:
        return {person_id: [] for person_id in person_ids}


class FakeVectorRepository:
    def __init__(self, evidence: list[CandidateEvidence]) -> None:
        self.evidence = evidence
        self.candidate_filter: set[UUID] | None = None

    async def search(
        self,
        embedding: Sequence[float],
        *,
        candidate_ids: set[UUID] | None,
        limit: int,
    ) -> list[CandidateEvidence]:
        self.candidate_filter = candidate_ids
        return [
            item
            for item in self.evidence
            if candidate_ids is None or item.person_id in candidate_ids
        ][:limit]


class FakeGraphRepository:
    def __init__(self, ids: set[UUID]) -> None:
        self.ids = ids

    async def sync_person(self, snapshot: object) -> None:
        return None

    async def search_ids(self, intent: CandidateSearchIntent, *, limit: int) -> set[UUID]:
        return set(list(self.ids)[:limit])

    async def paths(
        self,
        person_ids: set[UUID],
        *,
        max_hops: int,
        limit: int,
    ) -> list[GraphPath]:
        return []

    async def close(self) -> None:
        return None


async def test_hybrid_retriever_intersects_hard_and_graph_constraints() -> None:
    candidate_a, candidate_b, candidate_c = uuid4(), uuid4(), uuid4()
    profiles = {
        person_id: CandidateProfile(person_id=person_id, full_name=name)
        for person_id, name in (
            (candidate_a, "Ada"),
            (candidate_b, "Grace"),
            (candidate_c, "Linus"),
        )
    }
    vector_repository = FakeVectorRepository(
        [
            CandidateEvidence(
                person_id=person_id,
                chunk_id=uuid4(),
                source=EvidenceSource.VECTOR,
                content="Relevant evidence",
                score=score,
            )
            for person_id, score in ((candidate_a, 0.7), (candidate_b, 0.9), (candidate_c, 1.0))
        ]
    )
    retriever = HybridRetriever(
        structured_repository=FakeStructuredRepository(
            {candidate_a, candidate_b},
            profiles,
        ),
        vector_repository=vector_repository,
        embedding_service=EmbeddingService(
            FakeEmbeddingProvider(), expected_dimension=2, batch_size=10
        ),
        graph_repository=FakeGraphRepository({candidate_b, candidate_c}),
        ranker=CompositeRanker(),
    )
    intent = CandidateSearchIntent(
        role="backend",
        required_domains=["fintech"],
        semantic_query="distributed payments",
    )

    result = await retriever.search("find backend fintech", intent, limit=10)

    assert [match.candidate_id for match in result.candidates] == [candidate_b]
    assert vector_repository.candidate_filter == {candidate_a, candidate_b}
    assert result.strategy == [
        RetrievalOperation.STRUCTURED,
        RetrievalOperation.VECTOR,
        RetrievalOperation.GRAPH,
    ]


async def test_hard_location_filter_with_no_matches_never_falls_back_to_vector_search() -> None:
    candidate_id = uuid4()
    vector_repository = FakeVectorRepository(
        [
            CandidateEvidence(
                person_id=candidate_id,
                chunk_id=uuid4(),
                source=EvidenceSource.VECTOR,
                content="A highly similar candidate from another city.",
                score=1.0,
            )
        ]
    )
    retriever = HybridRetriever(
        structured_repository=FakeStructuredRepository(set(), {}),
        vector_repository=vector_repository,
        embedding_service=EmbeddingService(
            FakeEmbeddingProvider(), expected_dimension=2, batch_size=10
        ),
        ranker=CompositeRanker(),
    )

    result = await retriever.search(
        "backend developer in Moscow, otherwise return nobody",
        CandidateSearchIntent(location={"city": "Moscow"}, semantic_query="backend developer"),
        limit=20,
    )

    assert result.candidates == []
    assert result.strategy == [RetrievalOperation.STRUCTURED]
    assert vector_repository.candidate_filter is None
