import json
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.protocols import LanguageModelProvider
from app.retrieval.models import CandidateMatch


class Reranker(Protocol):
    async def rerank(
        self,
        query: str,
        candidates: Sequence[CandidateMatch],
    ) -> list[CandidateMatch]: ...


class RerankItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    relevance: float = Field(ge=0, le=1)


class RerankResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RerankItem]


class LLMReranker:
    _INSTRUCTIONS = """Rerank only the supplied candidate IDs using only supplied evidence.
Do not add or remove facts. Return every supplied ID at most once, in descending relevance."""

    def __init__(self, provider: LanguageModelProvider, *, top_n: int = 20) -> None:
        self.provider = provider
        self.top_n = top_n

    async def rerank(
        self,
        query: str,
        candidates: Sequence[CandidateMatch],
    ) -> list[CandidateMatch]:
        head = list(candidates[: self.top_n])
        tail = list(candidates[self.top_n :])
        if len(head) < 2:
            return [*head, *tail]
        payload = [
            {
                "candidate_id": str(candidate.candidate_id),
                "score": candidate.score,
                "evidence": [item.content for item in candidate.evidence[:5]],
            }
            for candidate in head
        ]
        result = await self.provider.structured_output(
            instructions=self._INSTRUCTIONS,
            prompt=json.dumps({"query": query, "candidates": payload}),
            response_model=RerankResult,
        )
        by_id = {candidate.candidate_id: candidate for candidate in head}
        ordered: list[CandidateMatch] = []
        seen: set[UUID] = set()
        for item in result.items:
            candidate = by_id.get(item.candidate_id)
            if candidate is not None and item.candidate_id not in seen:
                ordered.append(candidate)
                seen.add(item.candidate_id)
        ordered.extend(candidate for candidate in head if candidate.candidate_id not in seen)
        return [*ordered, *tail]
