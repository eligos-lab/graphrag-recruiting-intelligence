from typing import Any
from uuid import uuid4

import pytest

from app.generation.evidence import (
    EvidenceAnswer,
    EvidenceAnswerGenerator,
    GeneratedClaim,
    UnsupportedEvidenceError,
)
from app.retrieval.models import (
    CandidateEvidence,
    CandidateMatch,
    ClaimKind,
    EvidenceSource,
    ScoreBreakdown,
)


class FakeLanguageProvider:
    model = "test-model"

    def __init__(self, output: EvidenceAnswer) -> None:
        self.output = output

    async def generate(self, *, instructions: str, prompt: str) -> str:
        return self.output.answer

    async def structured_output(self, **_: Any) -> Any:
        return self.output


def candidate_match() -> tuple[CandidateMatch, object]:
    person_id = uuid4()
    chunk_id = uuid4()
    return (
        CandidateMatch(
            candidate_id=person_id,
            full_name="Ada Lovelace",
            score=0.9,
            breakdown=ScoreBreakdown(),
            evidence=[
                CandidateEvidence(
                    person_id=person_id,
                    chunk_id=chunk_id,
                    source=EvidenceSource.VECTOR,
                    content="Built fintech fraud detection systems.",
                    score=0.9,
                )
            ],
        ),
        chunk_id,
    )


async def test_evidence_generator_accepts_only_cited_claims() -> None:
    candidate, chunk_id = candidate_match()
    output = EvidenceAnswer(
        answer="Ada has documented fintech experience.",
        claims=[
            GeneratedClaim(
                candidate_id=candidate.candidate_id,
                claim="Has fintech experience",
                kind=ClaimKind.FACT,
                confidence=1,
                evidence_ids=[chunk_id],
            )
        ],
    )

    answer = await EvidenceAnswerGenerator(FakeLanguageProvider(output)).generate(
        "Find fintech engineers", [candidate]
    )

    assert answer == output


async def test_evidence_generator_rejects_unknown_evidence_ids() -> None:
    candidate, _ = candidate_match()
    output = EvidenceAnswer(
        answer="Unsupported answer",
        claims=[
            GeneratedClaim(
                candidate_id=candidate.candidate_id,
                claim="Unknown claim",
                kind=ClaimKind.FACT,
                confidence=1,
                evidence_ids=[uuid4()],
            )
        ],
    )

    with pytest.raises(UnsupportedEvidenceError, match="unknown evidence"):
        await EvidenceAnswerGenerator(FakeLanguageProvider(output)).generate("query", [candidate])


async def test_evidence_generator_requires_reason_for_inference() -> None:
    candidate, chunk_id = candidate_match()
    output = EvidenceAnswer(
        answer="Inference",
        claims=[
            GeneratedClaim(
                candidate_id=candidate.candidate_id,
                claim="Likely cloud-native background",
                kind=ClaimKind.INFERENCE,
                confidence=0.7,
                evidence_ids=[chunk_id],
            )
        ],
    )

    with pytest.raises(UnsupportedEvidenceError, match="explicit reason"):
        await EvidenceAnswerGenerator(FakeLanguageProvider(output)).generate("query", [candidate])
