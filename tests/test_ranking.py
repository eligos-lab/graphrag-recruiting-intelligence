from uuid import uuid4

import pytest

from app.ranking.scoring import CompositeRanker
from app.retrieval.intent import CandidateSearchIntent, LocationIntent
from app.retrieval.models import (
    CandidateEvidence,
    CandidateProfile,
    EvidenceSource,
    GraphPath,
)


def test_composite_ranking_has_explainable_weighted_breakdown() -> None:
    person_id = uuid4()
    chunk_id = uuid4()
    intent = CandidateSearchIntent(
        role="backend engineer",
        seniority="senior",
        location=LocationIntent(country="Germany"),
        min_years_experience=5,
        required_skills=["Kafka"],
        required_domains=["fintech"],
        preferred_domains=["cybersecurity"],
    )
    profile = CandidateProfile(
        person_id=person_id,
        full_name="Ada Lovelace",
        country="Germany",
        current_title="Senior Backend Engineer",
        years_experience=8,
        skills=["Kafka"],
        domains=["fintech", "cybersecurity"],
    )
    evidence = CandidateEvidence(
        person_id=person_id,
        chunk_id=chunk_id,
        source=EvidenceSource.VECTOR,
        content="Built event-driven payment services with Kafka.",
        score=0.8,
    )
    path = GraphPath(
        person_id=person_id,
        nodes=["Ada Lovelace", "Fintech"],
        relationships=["SPECIALIZES_IN"],
        evidence_ids=[chunk_id],
        score=0.5,
    )

    match = CompositeRanker().rank(
        intent,
        {person_id: profile},
        {person_id: [evidence]},
        [path],
        limit=10,
    )[0]

    assert match.score == pytest.approx(0.89)
    assert match.breakdown.semantic == 0.8
    assert match.breakdown.skills == 1
    assert match.breakdown.domains == 1
    assert match.breakdown.graph == 0.5
    assert match.current_title == "Senior Backend Engineer"
    assert match.years_experience == 8
    assert match.skills == ["Kafka"]
    assert match.domains == ["fintech", "cybersecurity"]
    assert match.reasons
    assert all(reason.evidence_ids == [chunk_id] for reason in match.reasons)
