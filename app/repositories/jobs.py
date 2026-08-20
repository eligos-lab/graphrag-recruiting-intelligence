from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import IngestionJobModel
from app.ingestion.jobs import (
    IngestionJob,
    IngestionJobOptions,
    IngestionJobStatus,
)


class IngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        path: str,
        source_name: str | None,
        options: IngestionJobOptions,
    ) -> IngestionJob:
        model = IngestionJobModel(
            status=IngestionJobStatus.QUEUED.value,
            path=path,
            source_name=source_name,
            options=options.model_dump(),
        )
        self.session.add(model)
        await self.session.commit()
        return self._job(model)

    async def get(self, job_id: UUID) -> IngestionJob | None:
        model = await self.session.get(IngestionJobModel, job_id)
        return self._job(model) if model is not None else None

    async def set_task_id(self, job_id: UUID, task_id: str) -> None:
        model = await self._required(job_id)
        model.celery_task_id = task_id
        await self.session.commit()

    async def update_status(
        self,
        job_id: UUID,
        status: IngestionJobStatus,
        *,
        report: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        model = await self._required(job_id)
        model.status = status.value
        model.report = report
        model.error = error
        await self.session.commit()

    async def _required(self, job_id: UUID) -> IngestionJobModel:
        model = await self.session.get(IngestionJobModel, job_id)
        if model is None:
            raise LookupError(f"Unknown ingestion job: {job_id}")
        return model

    @staticmethod
    def _job(model: IngestionJobModel) -> IngestionJob:
        return IngestionJob(
            id=model.id,
            status=IngestionJobStatus(model.status),
            path=model.path,
            source_name=model.source_name,
            options=IngestionJobOptions.model_validate(model.options),
            celery_task_id=model.celery_task_id,
            report=model.report,
            error=model.error,
        )
