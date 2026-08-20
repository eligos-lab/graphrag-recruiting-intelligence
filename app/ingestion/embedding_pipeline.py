import json
import logging

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.chunking import ResumeChunker
from app.ingestion.parsers.structured import StructuredResumeParser
from app.ingestion.results import IngestionError
from app.ingestion.schemas import DocumentType, SourceDocument
from app.repositories.chunks import ChunkPersistOutcome, ChunkRepository
from app.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingReport(BaseModel):
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list[IngestionError] = Field(default_factory=list)


class StructuredEmbeddingPipeline:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        *,
        chunker: ResumeChunker | None = None,
        parser: StructuredResumeParser | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.chunker = chunker or ResumeChunker()
        self.parser = parser or StructuredResumeParser()

    async def run(
        self,
        session: AsyncSession,
        *,
        limit: int | None = None,
    ) -> EmbeddingReport:
        repository = ChunkRepository(session)
        contexts = await repository.list_structured_contexts(limit=limit)
        report = EmbeddingReport(total=len(contexts))

        for context in contexts:
            try:
                payload = json.loads(context.raw_text)
                if not isinstance(payload, dict):
                    raise ValueError("Structured raw document must contain a JSON object")
                source_document = SourceDocument(
                    source=context.source,
                    external_id=context.external_id,
                    document_type=DocumentType(context.document_type),
                    raw_text=context.raw_text,
                    payload=payload,
                    metadata=context.metadata,
                )
                resume = self.parser.parse(source_document)
                chunks = self.chunker.chunk(
                    resume,
                    person_id=context.person_id,
                    document_id=context.document_id,
                    company_ids=context.company_ids,
                )

                if await repository.is_current(
                    context.document_id,
                    chunks,
                    self.embedding_service.provider.model,
                    self.embedding_service.expected_dimension,
                ):
                    report.unchanged += 1
                    continue

                embeddings = await self.embedding_service.embed([chunk.content for chunk in chunks])
                async with session.begin_nested():
                    outcome = await repository.upsert(
                        chunks,
                        embeddings,
                        self.embedding_service.provider.model,
                    )
                if outcome is ChunkPersistOutcome.CREATED:
                    report.created += 1
                else:
                    report.updated += 1
            except Exception as error:
                logger.exception(
                    "Structured embedding failed",
                    extra={"source": context.source, "external_id": context.external_id},
                )
                report.failed += 1
                report.errors.append(
                    IngestionError(
                        source=context.source,
                        external_id=context.external_id,
                        error_type=type(error).__name__,
                        message=str(error),
                    )
                )

        await session.commit()
        return report
