import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.graph.neo4j import Neo4jGraphRepository
from app.graph.sync import GraphSyncService
from app.ingestion.chunking import ResumeChunker
from app.ingestion.embedding_pipeline import StructuredEmbeddingPipeline
from app.ingestion.jobs import IngestionJobStatus
from app.ingestion.parsers.llm import LLMResumeParser
from app.ingestion.pipeline import StructuredIngestionPipeline
from app.ingestion.sources import (
    BaseDataSource,
    CsvResumeSource,
    JsonResumeSource,
    PdfResumeSource,
    TextResumeSource,
)
from app.ingestion.unstructured_pipeline import UnstructuredIngestionPipeline
from app.llm.factory import (
    EmbeddingProviderClient,
    LanguageModelProviderClient,
    create_embedding_provider,
    create_language_model_provider,
)
from app.repositories.graph_snapshot import GraphSnapshotRepository
from app.repositories.jobs import IngestionJobRepository
from app.services.embeddings import EmbeddingService
from app.workers.celery_app import celery_app


def _source(path: Path, source_name: str | None, settings: Settings) -> BaseDataSource:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return CsvResumeSource(path, source_name=source_name)
    if suffix in {".json", ".jsonl"}:
        return JsonResumeSource(path, source_name=source_name)
    if suffix == ".pdf":
        return PdfResumeSource(
            path,
            source_name=source_name,
            max_file_size_mb=settings.pdf_max_file_size_mb,
        )
    if suffix in {".txt", ".md"}:
        return TextResumeSource(path, source_name=source_name)
    raise ValueError(f"Unsupported ingestion format: {suffix}")


async def _execute_job(job_id: UUID) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    embedding_provider: EmbeddingProviderClient | None = None
    language_provider: LanguageModelProviderClient | None = None
    graph_repository: Neo4jGraphRepository | None = None
    async with session_factory() as session:
        repository = IngestionJobRepository(session)
        job = await repository.get(job_id)
        if job is None:
            await engine.dispose()
            raise LookupError(f"Unknown ingestion job: {job_id}")
        await repository.update_status(job_id, IngestionJobStatus.RUNNING)
        try:
            source = _source(Path(job.path), job.source_name, settings)
            reports: dict[str, Any] = {}
            embedding_service = None
            if job.options.generate_embeddings:
                embedding_provider = create_embedding_provider(settings)
                embedding_service = EmbeddingService(
                    embedding_provider,
                    expected_dimension=settings.embedding_dimension,
                    batch_size=settings.embedding_batch_size,
                )

            if source.source_type in {"csv", "json"}:
                ingestion_report = await StructuredIngestionPipeline().ingest(source, session)
                reports["ingestion"] = ingestion_report.model_dump(mode="json")
                if embedding_service is not None:
                    embedding_report = await StructuredEmbeddingPipeline(
                        embedding_service,
                        chunker=ResumeChunker(settings.chunk_max_characters),
                    ).run(session)
                    reports["embeddings"] = embedding_report.model_dump(mode="json")
            else:
                language_provider = create_language_model_provider(settings)
                ingestion_report = await UnstructuredIngestionPipeline(
                    LLMResumeParser(
                        language_provider,
                        max_input_characters=settings.llm_max_input_characters,
                    ),
                    embedding_service=embedding_service,
                    chunker=ResumeChunker(settings.chunk_max_characters),
                ).ingest(source, session)
                reports["ingestion"] = ingestion_report.model_dump(mode="json")

            if job.options.update_graph:
                graph_repository = Neo4jGraphRepository.connect(
                    uri=settings.neo4j_uri,
                    user=settings.neo4j_user,
                    password=settings.neo4j_password.get_secret_value(),
                    database=settings.neo4j_database,
                )
                graph_report = await GraphSyncService(
                    GraphSnapshotRepository(session),
                    graph_repository,
                ).sync()
                reports["graph"] = graph_report.model_dump(mode="json")

            await repository.update_status(
                job_id,
                IngestionJobStatus.SUCCEEDED,
                report=reports,
            )
            return reports
        except Exception as error:
            await session.rollback()
            await repository.update_status(
                job_id,
                IngestionJobStatus.FAILED,
                error=str(error),
            )
            raise
        finally:
            if embedding_provider is not None:
                await embedding_provider.close()
            if language_provider is not None:
                await language_provider.close()
            if graph_repository is not None:
                await graph_repository.close()
            await engine.dispose()


@celery_app.task(name="graphrag.run_ingestion_job")  # type: ignore[untyped-decorator]
def run_ingestion_job(job_id: str) -> dict[str, Any]:
    return asyncio.run(_execute_job(UUID(job_id)))
