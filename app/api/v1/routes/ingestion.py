import json
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.dependencies import SessionDependency, SettingsDependency
from app.ingestion.demo_corpus import demo_candidate_records
from app.ingestion.jobs import (
    SUPPORTED_INGESTION_SUFFIXES,
    IngestionBatch,
    IngestionJob,
    IngestionJobOptions,
    IngestionJobRequest,
    IngestionJobStatus,
    resolve_ingestion_path,
)
from app.repositories.jobs import IngestionJobRepository
from app.workers.celery_app import celery_app

router = APIRouter()


async def _enqueue_job(
    *,
    path: Path,
    source_name: str | None,
    generate_embeddings: bool,
    update_graph: bool,
    session: SessionDependency,
) -> IngestionJob:
    repository = IngestionJobRepository(session)
    job = await repository.create(
        path=str(path),
        source_name=source_name,
        options=IngestionJobOptions(
            generate_embeddings=generate_embeddings,
            update_graph=update_graph,
        ),
    )
    try:
        task = celery_app.send_task("graphrag.run_ingestion_job", args=[str(job.id)])
        await repository.set_task_id(job.id, task.id)
    except Exception as error:
        await repository.update_status(
            job.id,
            IngestionJobStatus.FAILED,
            error="Unable to enqueue ingestion job",
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue is unavailable",
        ) from error
    updated = await repository.get(job.id)
    if updated is None:
        raise RuntimeError("Created ingestion job disappeared")
    return updated


@router.post("", response_model=IngestionJob, status_code=status.HTTP_202_ACCEPTED)
async def create_ingestion_job(
    request: IngestionJobRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> IngestionJob:
    try:
        path = resolve_ingestion_path(settings.ingestion_data_root, request.path)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion file not found",
        ) from error

    return await _enqueue_job(
        path=path,
        source_name=request.source_name,
        generate_embeddings=request.generate_embeddings,
        update_graph=request.update_graph,
        session=session,
    )


@router.post("/upload", response_model=IngestionJob, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume_data(
    session: SessionDependency,
    settings: SettingsDependency,
    file: Annotated[UploadFile, File(...)],
    source_name: str | None = Form(default=None, max_length=255),
    generate_embeddings: bool = Form(default=True),
    update_graph: bool = Form(default=True),
) -> IngestionJob:
    suffix = Path(file.filename or "").suffix.casefold()
    if suffix not in SUPPORTED_INGESTION_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Supported formats: CSV, JSON, JSONL, PDF, TXT, MD",
        )
    upload_dir = settings.ingestion_data_root.resolve() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid4().hex}{suffix}"
    limit = settings.upload_max_file_size_mb * 1024 * 1024
    written = 0
    try:
        with destination.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds {settings.upload_max_file_size_mb} MB limit",
                    )
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return await _enqueue_job(
        path=destination,
        source_name=source_name or f"upload-{uuid4().hex[:8]}",
        generate_embeddings=generate_embeddings,
        update_graph=update_graph,
        session=session,
    )


@router.post("/upload-archive", response_model=IngestionBatch, status_code=status.HTTP_202_ACCEPTED)
async def upload_resume_archive(
    session: SessionDependency,
    settings: SettingsDependency,
    file: Annotated[UploadFile, File(...)],
) -> IngestionBatch:
    if Path(file.filename or "").suffix.casefold() != ".zip":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only ZIP archives are supported"
        )
    upload_dir = settings.ingestion_data_root.resolve() / "uploads" / uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=False)
    archive_path = upload_dir / "archive.zip"
    limit = settings.upload_max_file_size_mb * 1024 * 1024
    written = 0
    try:
        with archive_path.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Archive is too large",
                    )
                output.write(chunk)
        with ZipFile(archive_path) as archive:
            entries = [item for item in archive.infolist() if not item.is_dir()]
            if len(entries) > 100 or sum(item.file_size for item in entries) > limit * 4:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Archive contains too much data",
                )
            supported = [
                item
                for item in entries
                if Path(item.filename).suffix.casefold() in SUPPORTED_INGESTION_SUFFIXES
            ]
            if not supported:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Archive has no supported resume files",
                )
            paths: list[Path] = []
            for number, entry in enumerate(supported, start=1):
                destination = (
                    upload_dir / f"resume-{number}{Path(entry.filename).suffix.casefold()}"
                )
                with archive.open(entry) as source, destination.open("xb") as output:
                    output.write(source.read())
                paths.append(destination)
    except BadZipFile as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ZIP archive"
        ) from error
    finally:
        await file.close()
    jobs = [
        await _enqueue_job(
            path=path,
            source_name=f"archive-{Path(file.filename or 'archive').stem[:60]}-{position}",
            generate_embeddings=True,
            update_graph=True,
            session=session,
        )
        for position, path in enumerate(paths, start=1)
    ]
    skipped = [item.filename for item in entries if item not in supported]
    return IngestionBatch(jobs=jobs, skipped_files=skipped)


@router.post("/demo", response_model=IngestionJob, status_code=status.HTTP_202_ACCEPTED)
async def load_demo_corpus(
    session: SessionDependency,
    settings: SettingsDependency,
) -> IngestionJob:
    demo_dir = settings.ingestion_data_root.resolve() / "generated"
    demo_dir.mkdir(parents=True, exist_ok=True)
    destination = demo_dir / "fictional_demo_candidates_50.json"
    destination.write_text(
        json.dumps({"records": demo_candidate_records()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return await _enqueue_job(
        path=destination,
        source_name="fictional-demo-50",
        generate_embeddings=True,
        update_graph=True,
        session=session,
    )


@router.get("/{job_id}", response_model=IngestionJob)
async def get_ingestion_job(
    job_id: UUID,
    session: SessionDependency,
) -> IngestionJob:
    job = await IngestionJobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
