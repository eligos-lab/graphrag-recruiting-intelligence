import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.infrastructure.database.models import (
    PersonModel,
    RawDocumentModel,
    SkillAliasModel,
    SkillModel,
    TechnologyModel,
)
from app.ingestion.pipeline import StructuredIngestionPipeline
from app.ingestion.sources import JsonResumeSource


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


def write_records(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"records": records}), encoding="utf-8")


def candidate_record(external_id: str = "candidate-1") -> dict[str, object]:
    return {
        "id": external_id,
        "full_name": "Ada Lovelace",
        "country": "United Kingdom",
        "current_title": "Senior Backend Engineer",
        "years_experience": 8,
        "skills": ["Postgres", "Postgre SQL", "Python"],
        "technologies": ["AWS"],
        "domains": ["fintech"],
        "experience": [
            {
                "company": "Analytical Engines Ltd",
                "technologies": ["K8s"],
                "domains": ["fintech"],
            }
        ],
        "education": [{"university": "University of London", "country": "UK"}],
        "projects": [
            {
                "name": "Fraud Graph",
                "technologies": ["GNN"],
                "domains": ["cybersecurity"],
            }
        ],
    }


async def model_count(session: AsyncSession, model: type[object]) -> int:
    count = await session.scalar(select(func.count()).select_from(model))
    assert count is not None
    return count


async def test_ingestion_is_idempotent_and_persists_normalized_entities(
    tmp_path: Path,
    database_session: AsyncSession,
) -> None:
    path = tmp_path / "candidates.json"
    write_records(path, [candidate_record()])
    source = JsonResumeSource(path, source_name="fixture")
    pipeline = StructuredIngestionPipeline()

    first_report = await pipeline.ingest(source, database_session)
    second_report = await pipeline.ingest(source, database_session)

    assert first_report.created == 1
    assert second_report.unchanged == second_report.skipped == 1
    assert await model_count(database_session, RawDocumentModel) == 1
    assert await model_count(database_session, PersonModel) == 1
    assert await model_count(database_session, SkillModel) == 2
    assert await model_count(database_session, SkillAliasModel) == 3

    skills = list(await database_session.scalars(select(SkillModel)))
    assert {skill.normalized_name for skill in skills} == {"postgresql", "python"}

    technologies = list(await database_session.scalars(select(TechnologyModel)))
    assert {technology.name for technology in technologies} == {
        "Amazon Web Services",
        "Graph Neural Networks",
        "Kubernetes",
    }


async def test_changed_document_updates_existing_raw_document(
    tmp_path: Path,
    database_session: AsyncSession,
) -> None:
    path = tmp_path / "candidate.json"
    write_records(path, [candidate_record()])
    pipeline = StructuredIngestionPipeline()
    await pipeline.ingest(JsonResumeSource(path, source_name="fixture"), database_session)

    updated_candidate = candidate_record()
    updated_candidate["current_title"] = "Principal Backend Engineer"
    updated_candidate["skills"] = ["Postgres", "Python", "Kafka"]
    write_records(path, [updated_candidate])
    report = await pipeline.ingest(
        JsonResumeSource(path, source_name="fixture"),
        database_session,
    )

    assert report.updated == 1
    assert await model_count(database_session, RawDocumentModel) == 1
    assert await model_count(database_session, PersonModel) == 1
    person = await database_session.scalar(select(PersonModel))
    assert person is not None
    assert person.current_title == "Principal Backend Engineer"
    assert {skill.normalized_name for skill in person.skills} == {
        "kafka",
        "postgresql",
        "python",
    }


async def test_checksum_and_normalized_identity_deduplication(
    tmp_path: Path,
    database_session: AsyncSession,
) -> None:
    path = tmp_path / "candidate.json"
    write_records(path, [candidate_record()])
    pipeline = StructuredIngestionPipeline()
    await pipeline.ingest(JsonResumeSource(path, source_name="source-a"), database_session)

    duplicate_report = await pipeline.ingest(
        JsonResumeSource(path, source_name="source-b"),
        database_session,
    )
    assert duplicate_report.duplicates == duplicate_report.skipped == 1
    assert await model_count(database_session, RawDocumentModel) == 1

    write_records(path, [candidate_record(external_id="candidate-from-another-source")])
    identity_report = await pipeline.ingest(
        JsonResumeSource(path, source_name="source-b"),
        database_session,
    )

    assert identity_report.created == 1
    assert await model_count(database_session, RawDocumentModel) == 2
    assert await model_count(database_session, PersonModel) == 1


async def test_invalid_record_does_not_rollback_valid_records(
    tmp_path: Path,
    database_session: AsyncSession,
) -> None:
    path = tmp_path / "mixed.json"
    write_records(path, [candidate_record(), {"id": "invalid", "skills": ["Python"]}])

    report = await StructuredIngestionPipeline().ingest(
        JsonResumeSource(path, source_name="fixture"),
        database_session,
    )

    assert report.total == 2
    assert report.created == 1
    assert report.failed == 1
    assert report.errors[0].external_id == "invalid"
    assert await model_count(database_session, RawDocumentModel) == 1


async def test_idempotency_survives_new_database_sessions(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    path = tmp_path / "candidate.json"
    write_records(path, [candidate_record()])

    reports = []
    for _ in range(2):
        async with session_factory() as session:
            reports.append(
                await StructuredIngestionPipeline().ingest(
                    JsonResumeSource(path, source_name="fixture"),
                    session,
                )
            )

    async with session_factory() as session:
        raw_document_count = await model_count(session, RawDocumentModel)
        person_count = await model_count(session, PersonModel)
    await engine.dispose()

    assert reports[0].created == 1
    assert reports[1].unchanged == 1
    assert raw_document_count == person_count == 1
