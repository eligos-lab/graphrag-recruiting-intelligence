from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.routes.ingestion import celery_app
from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import get_database_session
from app.ingestion.jobs import resolve_ingestion_path
from app.main import create_app


def test_ingestion_job_path_is_confined_to_data_root(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    candidate_file = data_root / "candidate.json"
    candidate_file.write_text("{}", encoding="utf-8")

    assert resolve_ingestion_path(data_root, "candidate.json") == candidate_file.resolve()

    with pytest.raises(ValueError, match="inside"):
        resolve_ingestion_path(data_root, "../outside.json")


def test_ingestion_job_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_ingestion_path(tmp_path, "missing.json")


async def test_ingestion_job_api_persists_and_enqueues_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "candidate.json").write_text("{}", encoding="utf-8")
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[object]:
        async with session_factory() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_database_session] = override_session
    application.dependency_overrides[get_settings] = lambda: Settings(
        environment="test",
        database_url="sqlite+aiosqlite://",
        ingestion_data_root=data_root,
    )
    monkeypatch.setattr(
        celery_app,
        "send_task",
        lambda *args, **kwargs: SimpleNamespace(id="task-123"),
    )
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/ingestion/jobs",
            json={
                "path": "candidate.json",
                "generate_embeddings": False,
                "update_graph": False,
            },
        )
        fetched = await client.get(f"/api/v1/ingestion/jobs/{created.json()['id']}")
        uploaded = await client.post(
            "/api/v1/ingestion/jobs/upload",
            files={"file": ("batch.json", b'{"records": []}', "application/json")},
            data={"source_name": "test-upload", "generate_embeddings": "false"},
        )

    await engine.dispose()
    assert created.status_code == 202
    assert created.json()["status"] == "queued"
    assert created.json()["celery_task_id"] == "task-123"
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created.json()["id"]
    assert uploaded.status_code == 202
    assert uploaded.json()["source_name"] == "test-upload"
    assert list((data_root / "uploads").glob("*.json"))


async def test_archive_upload_enqueues_each_supported_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    archive = BytesIO()
    with ZipFile(archive, "w") as file:
        file.writestr("one.json", '{"records": []}')
        file.writestr("notes.txt", "A resume")
        file.writestr("ignored.exe", "not a resume")
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[object]:
        async with session_factory() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_database_session] = override_session
    application.dependency_overrides[get_settings] = lambda: Settings(
        environment="test", database_url="sqlite+aiosqlite://", ingestion_data_root=data_root
    )
    monkeypatch.setattr(celery_app, "send_task", lambda *args, **kwargs: SimpleNamespace(id="task"))
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ingestion/jobs/upload-archive",
            files={"file": ("resumes.zip", archive.getvalue(), "application/zip")},
        )

    await engine.dispose()
    assert response.status_code == 202
    assert len(response.json()["jobs"]) == 2
    assert response.json()["skipped_files"] == ["ignored.exe"]
