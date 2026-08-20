import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models import PersonModel, RawDocumentModel
from app.ingestion.chunking import ResumeChunker
from app.ingestion.parsers.llm import LLMResumeParser
from app.ingestion.results import IngestionError, IngestionReport, PersistOutcome
from app.ingestion.schemas import CanonicalResume, SourceDocument
from app.ingestion.sources.base import BaseDataSource
from app.repositories.chunks import ChunkRepository
from app.repositories.ingestion import IngestionRepository
from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class UnstructuredIngestionPipeline:
    def __init__(
        self,
        parser: LLMResumeParser,
        *,
        embedding_service: EmbeddingService | None = None,
        chunker: ResumeChunker | None = None,
    ) -> None:
        self.parser = parser
        self.embedding_service = embedding_service
        self.chunker = chunker or ResumeChunker()

    async def ingest(self, source: BaseDataSource, session: AsyncSession) -> IngestionReport:
        report = IngestionReport()
        repository = IngestionRepository(session)
        for document in source.iter_documents():
            report.total += 1
            try:
                resume = await self.parser.parse(document)
                async with session.begin_nested():
                    outcome = await repository.persist(document, resume)
                    if (
                        self.embedding_service is not None
                        and outcome is not PersistOutcome.DUPLICATE
                    ):
                        await self._embed(document, resume, session)
                self._record(report, outcome)
            except Exception as error:
                logger.exception(
                    "Unstructured ingestion failed",
                    extra={"source": document.source, "external_id": document.external_id},
                )
                report.failed += 1
                report.errors.append(
                    IngestionError(
                        source=document.source,
                        external_id=document.external_id,
                        error_type=type(error).__name__,
                        message=str(error),
                    )
                )
        await session.commit()
        return report

    async def _embed(
        self,
        document: SourceDocument,
        resume: CanonicalResume,
        session: AsyncSession,
    ) -> None:
        embedding_service = self.embedding_service
        if embedding_service is None:
            raise RuntimeError("Embedding service is not configured")
        raw_document = await session.scalar(
            select(RawDocumentModel)
            .where(
                RawDocumentModel.source == document.source,
                RawDocumentModel.external_id == document.external_id,
            )
            .options(selectinload(RawDocumentModel.person).selectinload(PersonModel.companies))
        )
        if raw_document is None or raw_document.person is None:
            raise RuntimeError("Persisted unstructured document has no candidate")
        chunks = self.chunker.chunk(
            resume,
            person_id=raw_document.person.id,
            document_id=raw_document.id,
            company_ids={
                company.normalized_name: company.id for company in raw_document.person.companies
            },
        )
        chunk_repository = ChunkRepository(session)
        if await chunk_repository.is_current(
            raw_document.id,
            chunks,
            embedding_service.provider.model,
            embedding_service.expected_dimension,
        ):
            return
        embeddings = await embedding_service.embed([chunk.content for chunk in chunks])
        await chunk_repository.upsert(
            chunks,
            embeddings,
            embedding_service.provider.model,
        )

    @staticmethod
    def _record(report: IngestionReport, outcome: PersistOutcome) -> None:
        if outcome is PersistOutcome.CREATED:
            report.created += 1
        elif outcome is PersistOutcome.UPDATED:
            report.updated += 1
        elif outcome is PersistOutcome.UNCHANGED:
            report.unchanged += 1
            report.skipped += 1
        else:
            report.duplicates += 1
            report.skipped += 1
