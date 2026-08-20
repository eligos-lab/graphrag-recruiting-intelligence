import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.llm.protocols import LanguageModelProvider
from app.retrieval.models import CandidateMatch, ClaimKind


class GeneratedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    claim: str
    kind: ClaimKind
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[UUID]
    reason: str | None = None


class EvidenceAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    claims: list[GeneratedClaim]
    limitations: list[str] = Field(default_factory=list)


class UnsupportedEvidenceError(ValueError):
    pass


class EvidenceAnswerGenerator:
    _INSTRUCTIONS = """Answer only from supplied candidate evidence.
Every factual claim must cite one or more supplied evidence_ids. Label deductions as inference,
include confidence and reason, and still cite evidence. Never turn an inference into a fact.
Copy candidate_id and evidence_id values exactly, character for character, from the supplied JSON.
Never invent, transform, abbreviate, or regenerate an ID. Omit a claim if no supplied IDs
support it.
If evidence is insufficient, state that limitation instead of filling gaps."""

    def __init__(self, provider: LanguageModelProvider) -> None:
        self.provider = provider

    async def generate(
        self,
        query: str,
        candidates: list[CandidateMatch],
    ) -> EvidenceAnswer:
        payload = {
            "query": query,
            "candidates": [
                {
                    "candidate_id": str(candidate.candidate_id),
                    "name": candidate.full_name,
                    "score": candidate.score,
                    "evidence": self._unique_evidence(candidate),
                }
                for candidate in candidates
            ],
        }
        answer = await self.provider.structured_output(
            instructions=self._INSTRUCTIONS,
            prompt=json.dumps(payload, ensure_ascii=False),
            response_model=EvidenceAnswer,
        )
        self._validate(answer, candidates)
        return answer

    @staticmethod
    def _unique_evidence(candidate: CandidateMatch, *, limit: int = 12) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        seen: set[UUID] = set()
        for item in candidate.evidence:
            if item.chunk_id is None or item.chunk_id in seen:
                continue
            seen.add(item.chunk_id)
            result.append(
                {
                    "evidence_id": str(item.chunk_id),
                    "content": item.content,
                    "source": item.source.value,
                }
            )
            if len(result) >= limit:
                break
        return result

    @staticmethod
    def _validate(answer: EvidenceAnswer, candidates: list[CandidateMatch]) -> None:
        evidence_by_candidate = {
            candidate.candidate_id: {
                item.chunk_id for item in candidate.evidence if item.chunk_id is not None
            }
            for candidate in candidates
        }
        for claim in answer.claims:
            available = evidence_by_candidate.get(claim.candidate_id)
            if available is None:
                raise UnsupportedEvidenceError(
                    f"Unknown candidate in generated claim: {claim.candidate_id}"
                )
            if not claim.evidence_ids:
                raise UnsupportedEvidenceError("Every generated claim requires evidence")
            unknown = set(claim.evidence_ids) - available
            if unknown:
                raise UnsupportedEvidenceError(
                    f"Generated claim references unknown evidence: {sorted(map(str, unknown))}"
                )
            if claim.kind is ClaimKind.FACT and claim.confidence != 1:
                raise UnsupportedEvidenceError("Facts must use confidence 1")
            if claim.kind is ClaimKind.INFERENCE and not claim.reason:
                raise UnsupportedEvidenceError("Inferences require an explicit reason")
