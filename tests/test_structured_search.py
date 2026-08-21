import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.ingestion.pipeline import StructuredIngestionPipeline
from app.ingestion.sources import JsonResumeSource
from app.repositories.search import SqlAlchemyStructuredSearchRepository
from app.retrieval.intent import CandidateSearchIntent, LocationIntent


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_structured_search_uses_hard_filters_and_alias_normalization(
    tmp_path: Path,
    database_session: AsyncSession,
) -> None:
    source_path = tmp_path / "candidates.json"
    source_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "id": "match",
                        "full_name": "Ada Lovelace",
                        "country": "Germany",
                        "current_title": "Senior Backend Engineer",
                        "years_experience": 8,
                        "skills": ["PostgreSQL"],
                        "technologies": ["Amazon Web Services"],
                        "domains": ["fintech"],
                    },
                    {
                        "id": "miss",
                        "full_name": "Grace Hopper",
                        "country": "United States",
                        "current_title": "Platform Engineer",
                        "years_experience": 10,
                        "skills": ["Python"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    await StructuredIngestionPipeline().ingest(
        JsonResumeSource(source_path, source_name="fixture"),
        database_session,
    )
    repository = SqlAlchemyStructuredSearchRepository(database_session)

    person_ids = await repository.filter_ids(
        CandidateSearchIntent(
            role="backend",
            seniority="senior",
            location=LocationIntent(country="Germany"),
            min_years_experience=5,
            required_skills=["Postgres"],
            required_technologies=["AWS"],
            required_domains=["FinTech"],
        ),
        limit=20,
    )
    profiles = await repository.profiles(person_ids)

    assert len(person_ids) == 1
    profile = profiles[next(iter(person_ids))]
    assert profile.full_name == "Ada Lovelace"
    assert profile.skills == ["PostgreSQL"]

    # Resume sources disagree on whether MLOps is a skill or technology.
    # A stated competency must match either normalized category.
    skill_or_technology_ids = await repository.filter_ids(
        CandidateSearchIntent(required_technologies=["Postgres"]),
        limit=20,
    )
    assert skill_or_technology_ids == person_ids
