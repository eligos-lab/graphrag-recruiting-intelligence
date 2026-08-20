from time import perf_counter
from uuid import UUID

from pydantic import BaseModel, Field

from app.ingestion.normalization import normalize_name
from app.ranking.reranker import Reranker
from app.ranking.scoring import CompositeRanker
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import CandidateEvidence, CandidateMatch, EvidenceSource, GraphPath
from app.retrieval.planner import QueryPlanner, RetrievalOperation
from app.retrieval.protocols import (
    GraphSearchRepository,
    StructuredSearchRepository,
    VectorSearchRepository,
)
from app.services.embeddings import EmbeddingService


class RetrievalTimings(BaseModel):
    structured_search_ms: float = 0
    vector_search_ms: float = 0
    graph_search_ms: float = 0
    reranking_ms: float = 0


class HybridRetrievalResult(BaseModel):
    candidates: list[CandidateMatch]
    strategy: list[RetrievalOperation]
    timings: RetrievalTimings = Field(default_factory=RetrievalTimings)


class HybridRetriever:
    def __init__(
        self,
        *,
        structured_repository: StructuredSearchRepository,
        vector_repository: VectorSearchRepository,
        embedding_service: EmbeddingService,
        ranker: CompositeRanker,
        graph_repository: GraphSearchRepository | None = None,
        reranker: Reranker | None = None,
        candidate_pool_size: int = 100,
        vector_limit: int = 100,
        graph_limit: int = 100,
        max_graph_hops: int = 3,
    ) -> None:
        self.structured_repository = structured_repository
        self.vector_repository = vector_repository
        self.embedding_service = embedding_service
        self.ranker = ranker
        self.graph_repository = graph_repository
        self.reranker = reranker
        self.candidate_pool_size = candidate_pool_size
        self.vector_limit = vector_limit
        self.graph_limit = graph_limit
        self.max_graph_hops = max_graph_hops
        self.planner = QueryPlanner()

    async def search(
        self,
        query: str,
        intent: CandidateSearchIntent,
        *,
        limit: int,
    ) -> HybridRetrievalResult:
        plan = self.planner.plan(intent)
        timings = RetrievalTimings()

        started = perf_counter()
        structured_ids = await self.structured_repository.filter_ids(
            intent,
            limit=self.candidate_pool_size,
        )
        timings.structured_search_ms = self._elapsed_ms(started)

        vector_evidence: list[CandidateEvidence] = []
        if RetrievalOperation.VECTOR in plan.operations:
            started = perf_counter()
            embedding = (await self.embedding_service.embed([intent.semantic_query or query]))[0]
            vector_evidence = await self.vector_repository.search(
                embedding,
                candidate_ids=structured_ids if plan.has_hard_filters and structured_ids else None,
                limit=self.vector_limit,
            )
            timings.vector_search_ms = self._elapsed_ms(started)

        graph_ids: set[UUID] = set()
        graph_enabled = (
            RetrievalOperation.GRAPH in plan.operations and self.graph_repository is not None
        )
        if graph_enabled and self.graph_repository is not None:
            started = perf_counter()
            graph_ids = await self.graph_repository.search_ids(intent, limit=self.graph_limit)
            timings.graph_search_ms = self._elapsed_ms(started)

        pool = self._candidate_pool(
            plan.has_hard_filters,
            structured_ids,
            {item.person_id for item in vector_evidence},
            graph_ids,
            graph_enabled=graph_enabled,
        )
        profiles = await self.structured_repository.profiles(pool)
        evidence = await self.structured_repository.evidence(pool)
        for item in vector_evidence:
            if item.person_id in pool:
                evidence.setdefault(item.person_id, []).append(item)

        graph_paths = []
        if graph_enabled and self.graph_repository is not None and pool:
            started = perf_counter()
            graph_paths = await self.graph_repository.paths(
                pool,
                max_hops=self.max_graph_hops,
                limit=self.graph_limit,
            )
            graph_paths = self._relevant_paths(intent, graph_paths)
            timings.graph_search_ms += self._elapsed_ms(started)
            graph_evidence_seen: set[tuple[UUID, UUID]] = set()
            for path in graph_paths:
                for evidence_id in path.evidence_ids:
                    evidence_key = (path.person_id, evidence_id)
                    if evidence_key in graph_evidence_seen:
                        continue
                    graph_evidence_seen.add(evidence_key)
                    evidence.setdefault(path.person_id, []).append(
                        CandidateEvidence(
                            person_id=path.person_id,
                            chunk_id=evidence_id,
                            source=EvidenceSource.GRAPH,
                            content=" → ".join(path.nodes),
                            score=path.score,
                            metadata={"relationships": ",".join(path.relationships)},
                        )
                    )

        candidates = self.ranker.rank(
            intent,
            profiles,
            evidence,
            graph_paths,
            limit=limit,
        )
        if self.reranker is not None:
            started = perf_counter()
            candidates = await self.reranker.rerank(query, candidates)
            timings.reranking_ms = self._elapsed_ms(started)
        candidates.sort(
            key=lambda item: (-item.score, item.full_name.casefold(), str(item.candidate_id))
        )
        return HybridRetrievalResult(
            candidates=candidates[:limit],
            strategy=[
                operation
                for operation in plan.operations
                if operation is not RetrievalOperation.GRAPH or graph_enabled
            ],
            timings=timings,
        )

    @staticmethod
    def _candidate_pool(
        has_hard_filters: bool,
        structured_ids: set[UUID],
        vector_ids: set[UUID],
        graph_ids: set[UUID],
        *,
        graph_enabled: bool,
    ) -> set[UUID]:
        if has_hard_filters and structured_ids:
            return structured_ids & graph_ids if graph_enabled else structured_ids
        if vector_ids:
            return vector_ids
        if graph_enabled:
            return graph_ids
        if vector_ids:
            return vector_ids
        return structured_ids

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return (perf_counter() - started) * 1_000

    @staticmethod
    def _relevant_paths(
        intent: CandidateSearchIntent,
        paths: list[GraphPath],
    ) -> list[GraphPath]:
        terms = {
            normalize_name(value)
            for value in [
                *intent.required_domains,
                *intent.companies,
                *intent.projects,
            ]
        }
        if not terms:
            return paths
        return [
            path
            for path in paths
            if any(term in normalize_name(node) for term in terms for node in path.nodes)
        ]
