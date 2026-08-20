import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.parsers.structured import StructuredResumeParser
from app.ingestion.results import IngestionError, IngestionReport, PersistOutcome
from app.ingestion.sources.base import BaseDataSource
from app.repositories.ingestion import IngestionRepository

logger = logging.getLogger(__name__)


class StructuredIngestionPipeline:
    def __init__(self, parser: StructuredResumeParser | None = None) -> None:
        self.parser = parser or StructuredResumeParser()

    async def ingest(
        self,
        source: BaseDataSource,
        session: AsyncSession,
    ) -> IngestionReport:
        report = IngestionReport()
        repository = IngestionRepository(session)

        for document in source.iter_documents():
            report.total += 1
            try:
                resume = self.parser.parse(document)
                async with session.begin_nested():
                    outcome = await repository.persist(document, resume)
                self._record_outcome(report, outcome)
            except Exception as error:
                logger.exception(
                    "Structured ingestion failed",
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

    @staticmethod
    def _record_outcome(report: IngestionReport, outcome: PersistOutcome) -> None:
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
