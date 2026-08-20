from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.api.dependencies import ExternalHealth, get_external_health
from app.infrastructure.database.session import get_database_session
from app.main import create_app


class HealthySession:
    async def execute(self, _: object) -> None:
        return None


class UnhealthySession:
    async def execute(self, _: object) -> None:
        raise OperationalError("SELECT 1", {}, RuntimeError("database unavailable"))


@pytest.mark.parametrize(
    ("session", "expected_code", "expected_status", "database_ready"),
    [
        (HealthySession(), 200, "healthy", True),
        (UnhealthySession(), 503, "degraded", False),
    ],
)
async def test_health_endpoint(
    session: HealthySession | UnhealthySession,
    expected_code: int,
    expected_status: str,
    database_ready: bool,
) -> None:
    app = create_app()

    async def override_session() -> AsyncIterator[object]:
        yield session

    app.dependency_overrides[get_database_session] = override_session
    app.dependency_overrides[get_external_health] = lambda: ExternalHealth(
        redis=True,
        graph=True,
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == expected_code
    assert response.json()["status"] == expected_status
    assert response.json()["checks"]["database"] is database_ready
