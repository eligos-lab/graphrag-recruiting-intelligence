from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.infrastructure.database.models import PersonModel, RawDocumentModel
from app.ingestion.parsers.llm import LLMResumeParser
from app.ingestion.schemas import ExtractedResume
from app.ingestion.sources import TextResumeSource
from app.ingestion.unstructured_pipeline import UnstructuredIngestionPipeline


class FakeExtractionProvider:
    model = "test-model"

    async def generate(self, *, instructions: str, prompt: str) -> str:
        return ""

    async def structured_output(self, **_: Any) -> Any:
        return ExtractedResume(
            full_name="Ada Lovelace",
            current_title="Backend Engineer",
            skills=["Python", "Postgres"],
            domains=["fintech"],
        )


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_text_resume_uses_validated_llm_extraction_and_idempotent_persistence(
    tmp_path: Path,
    database_session: AsyncSession,
) -> None:
    path = tmp_path / "resume.txt"
    path.write_text("Ada Lovelace\nBackend Engineer\nPython, Postgres\nFintech", encoding="utf-8")
    pipeline = UnstructuredIngestionPipeline(LLMResumeParser(FakeExtractionProvider()))
    source = TextResumeSource(path, source_name="uploaded-resume")

    first = await pipeline.ingest(source, database_session)
    second = await pipeline.ingest(source, database_session)

    people = await database_session.scalar(select(func.count()).select_from(PersonModel))
    documents = await database_session.scalar(select(func.count()).select_from(RawDocumentModel))
    assert first.created == 1
    assert second.unchanged == 1
    assert people == documents == 1
