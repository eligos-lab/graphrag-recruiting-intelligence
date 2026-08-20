from collections.abc import AsyncIterator
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.inference.engine import InferenceEngine
from app.inference.models import InferenceProposal, InferenceStatus, InferenceType
from app.infrastructure.database.base import Base
from app.infrastructure.database.models import CandidateInferenceModel, PersonModel
from app.repositories.inferences import InferenceRepository
from app.retrieval.models import CandidateEvidence, CandidateProfile, EvidenceSource


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def evidence(person_id: object, content: str) -> CandidateEvidence:
    return CandidateEvidence(
        person_id=person_id,
        chunk_id=uuid4(),
        source=EvidenceSource.STRUCTURED,
        content=content,
        score=1,
    )


def test_expertise_inference_requires_multiple_evidence_chunks() -> None:
    person_id = uuid4()
    profile = CandidateProfile(
        person_id=person_id,
        full_name="Ada Lovelace",
        domains=["fintech"],
    )
    items = [
        evidence(person_id, "Built fintech payments."),
        evidence(person_id, "Led fintech fraud detection."),
    ]

    proposals = InferenceEngine().infer_expertise(profile, items)

    assert len(proposals) == 1
    assert proposals[0].inference_type is InferenceType.EXPERTISE
    assert proposals[0].status is InferenceStatus.UNVERIFIED
    assert proposals[0].confidence < 1
    assert len(proposals[0].evidence_ids) == 2


def test_relationship_inference_explicitly_marks_unverified_date_overlap() -> None:
    person_id = uuid4()
    profile = CandidateProfile(
        person_id=person_id,
        full_name="Ada",
        companies=["Analytical Engines"],
    )
    peer = CandidateProfile(
        person_id=uuid4(),
        full_name="Grace",
        companies=["Analytical Engines"],
    )

    proposal = InferenceEngine().infer_relationship(
        profile,
        peer,
        [evidence(person_id, "Worked at Analytical Engines")],
    )

    assert proposal is not None
    assert proposal.inference_type is InferenceType.RELATIONSHIP
    assert "not verified" in proposal.reason


async def test_inference_persistence_is_idempotent(database_session: AsyncSession) -> None:
    person = PersonModel(
        full_name="Ada",
        source="fixture",
        source_id="ada",
        companies=[],
        skills=[],
        technologies=[],
        projects=[],
        universities=[],
        domains=[],
    )
    database_session.add(person)
    await database_session.flush()
    proposal = InferenceProposal(
        person_id=person.id,
        inference_type=InferenceType.EXPERTISE,
        claim="Likely has sustained expertise in fintech",
        confidence=0.7,
        reason="Two evidence chunks",
        evidence_ids=[uuid4(), uuid4()],
    )
    repository = InferenceRepository(database_session)

    await repository.upsert([proposal])
    await repository.upsert([proposal.model_copy(update={"confidence": 0.8})])

    count = await database_session.scalar(select(func.count()).select_from(CandidateInferenceModel))
    stored = await repository.list_for_person(person.id)
    assert count == 1
    assert stored[0].confidence == 0.8
