from uuid import uuid4

from app.ingestion.chunking import ChunkSection, ResumeChunker
from app.ingestion.schemas import (
    CanonicalResume,
    EducationItem,
    ExperienceItem,
    ProjectItem,
)


def test_chunker_preserves_semantic_sections_and_evidence_metadata() -> None:
    person_id = uuid4()
    document_id = uuid4()
    company_id = uuid4()
    resume = CanonicalResume(
        source="fixture",
        external_id="candidate-1",
        full_name="Ada Lovelace",
        current_title="Senior Backend Engineer",
        summary="Builds reliable payment infrastructure.",
        skills=["Python", "Kafka"],
        technologies=["Kubernetes"],
        domains=["fintech"],
        experience=[
            ExperienceItem(
                company="Analytical Engines Ltd",
                title="Backend Engineer",
                description="Built distributed transaction processing.",
                technologies=["Kafka"],
            )
        ],
        projects=[ProjectItem(name="Fraud Graph", technologies=["GraphSAGE"])],
        education=[EducationItem(university="University of London", degree="MSc")],
    )

    chunks = ResumeChunker().chunk(
        resume,
        person_id=person_id,
        document_id=document_id,
        company_ids={"analytical engines ltd": company_id},
    )

    assert {chunk.section for chunk in chunks} == set(ChunkSection)
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    experience = next(chunk for chunk in chunks if chunk.section is ChunkSection.EXPERIENCE)
    assert experience.content.startswith("EXPERIENCE: Analytical Engines Ltd")
    assert experience.metadata["company_id"] == str(company_id)
    assert all(chunk.metadata["document_id"] == str(document_id) for chunk in chunks)


def test_long_section_splits_on_boundaries_and_repeats_section_header() -> None:
    description = " ".join(
        f"Built subsystem {index} with measurable reliability improvements." for index in range(30)
    )
    resume = CanonicalResume(
        source="fixture",
        external_id="candidate-2",
        full_name="Grace Hopper",
        experience=[ExperienceItem(company="Compiler Systems", description=description)],
    )

    chunks = ResumeChunker(max_characters=300).chunk(
        resume,
        person_id=uuid4(),
        document_id=uuid4(),
    )
    experience_chunks = [chunk for chunk in chunks if chunk.section is ChunkSection.EXPERIENCE]

    assert len(experience_chunks) > 1
    assert all(len(chunk.content) <= 300 for chunk in experience_chunks)
    assert all(
        chunk.content.startswith("EXPERIENCE: Compiler Systems") for chunk in experience_chunks
    )
    assert [chunk.metadata["section_part"] for chunk in experience_chunks] == list(
        range(len(experience_chunks))
    )
