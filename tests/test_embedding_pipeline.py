import json
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.base import Base
from app.infrastructure.database.models import DocumentChunkModel
from app.ingestion.embedding_pipeline import StructuredEmbeddingPipeline
from app.ingestion.pipeline import StructuredIngestionPipeline
from app.ingestion.sources import JsonResumeSource
from app.services.embeddings import EmbeddingService

EMBEDDING_DIMENSION = 1_536


class DeterministicEmbeddingProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def model(self) -> str:
        return "deterministic-test-v1"

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIMENSION

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [
            [float(sum(text.encode("utf-8")) % 997) / 997, *([0.0] * (self.dimension - 1))]
            for text in texts
        ]


@pytest_asyncio.fixture
async def database_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


def write_candidate(path: Path, *, title: str = "Senior Backend Engineer") -> None:
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "id": "candidate-1",
                        "full_name": "Ada Lovelace",
                        "current_title": title,
                        "summary": "Builds reliable payment infrastructure.",
                        "skills": ["Python", "Kafka"],
                        "experience": [
                            {
                                "company": "Analytical Engines Ltd",
                                "title": "Backend Engineer",
                                "description": "Built distributed transaction processing.",
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


async def test_embedding_pipeline_is_idempotent_and_preserves_chunk_ids_on_update(
    tmp_path: Path,
    database_session: AsyncSession,
) -> None:
    path = tmp_path / "candidate.json"
    write_candidate(path)
    await StructuredIngestionPipeline().ingest(
        JsonResumeSource(path, source_name="fixture"),
        database_session,
    )

    provider = DeterministicEmbeddingProvider()
    pipeline = StructuredEmbeddingPipeline(
        EmbeddingService(
            provider,
            expected_dimension=EMBEDDING_DIMENSION,
            batch_size=2,
        )
    )

    first_report = await pipeline.run(database_session)
    chunks_before = list(
        await database_session.scalars(
            select(DocumentChunkModel).order_by(DocumentChunkModel.ordinal)
        )
    )
    ids_before = [chunk.id for chunk in chunks_before]
    calls_after_first_run = len(provider.calls)

    second_report = await pipeline.run(database_session)

    assert first_report.created == 1
    assert chunks_before
    assert all(len(chunk.embedding) == EMBEDDING_DIMENSION for chunk in chunks_before)
    assert second_report.unchanged == 1
    assert len(provider.calls) == calls_after_first_run

    write_candidate(path, title="Principal Backend Engineer")
    ingestion_report = await StructuredIngestionPipeline().ingest(
        JsonResumeSource(path, source_name="fixture"),
        database_session,
    )
    update_report = await pipeline.run(database_session)
    chunks_after = list(
        await database_session.scalars(
            select(DocumentChunkModel).order_by(DocumentChunkModel.ordinal)
        )
    )

    assert ingestion_report.updated == 1
    assert update_report.updated == 1
    assert [chunk.id for chunk in chunks_after] == ids_before
    assert "Principal Backend Engineer" in chunks_after[0].content
