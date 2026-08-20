import logging
from time import perf_counter
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.generation.evidence import (
    EvidenceAnswer,
    EvidenceAnswerGenerator,
    UnsupportedEvidenceError,
)
from app.retrieval.hybrid import HybridRetriever, RetrievalTimings
from app.retrieval.intent import CandidateSearchIntent, IntentParser
from app.retrieval.models import CandidateMatch
from app.retrieval.planner import RetrievalOperation

logger = logging.getLogger(__name__)


class SearchTimings(RetrievalTimings):
    intent_parsing_ms: float = 0
    generation_ms: float = 0
    total_ms: float = 0


class SearchExecutionResult(BaseModel):
    query_id: UUID = Field(default_factory=uuid4)
    parsed_intent: CandidateSearchIntent
    candidates: list[CandidateMatch]
    answer: EvidenceAnswer | None = None
    retrieval_strategy: list[RetrievalOperation]
    timings: SearchTimings


class SearchService:
    def __init__(
        self,
        *,
        intent_parser: IntentParser,
        retriever: HybridRetriever,
        answer_generator: EvidenceAnswerGenerator | None = None,
    ) -> None:
        self.intent_parser = intent_parser
        self.retriever = retriever
        self.answer_generator = answer_generator

    async def search(
        self,
        query: str,
        *,
        limit: int,
        generate_answer: bool = True,
    ) -> SearchExecutionResult:
        total_started = perf_counter()
        started = perf_counter()
        intent = await self.intent_parser.parse(query)
        intent_ms = self._elapsed_ms(started)
        retrieval = await self.retriever.search(query, intent, limit=limit)

        answer = None
        generation_ms = 0.0
        if generate_answer and self.answer_generator is not None and retrieval.candidates:
            started = perf_counter()
            try:
                answer = await self.answer_generator.generate(query, retrieval.candidates)
            except UnsupportedEvidenceError as error:
                logger.warning(
                    "Rejected unsupported generated answer",
                    extra={"error": str(error)},
                )
            generation_ms = self._elapsed_ms(started)

        timings = SearchTimings(
            **retrieval.timings.model_dump(),
            intent_parsing_ms=intent_ms,
            generation_ms=generation_ms,
            total_ms=self._elapsed_ms(total_started),
        )
        result = SearchExecutionResult(
            parsed_intent=intent,
            candidates=retrieval.candidates,
            answer=answer,
            retrieval_strategy=retrieval.strategy,
            timings=timings,
        )
        logger.info(
            "Candidate search completed",
            extra={
                "query_id": str(result.query_id),
                "retrieval_strategy": [item.value for item in result.retrieval_strategy],
                "candidate_count": len(result.candidates),
                **timings.model_dump(),
            },
        )
        return result

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return (perf_counter() - started) * 1_000
