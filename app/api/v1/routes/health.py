import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.infrastructure.database.session import get_database_session
from app.schemas.health import HealthChecks, HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()

SessionDependency = Annotated[AsyncSession, Depends(get_database_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get(
    "",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(
    response: Response,
    session: SessionDependency,
    settings: SettingsDependency,
) -> HealthResponse:
    database_ready = True
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database readiness check failed", exc_info=True)
        database_ready = False
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if database_ready else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        checks=HealthChecks(database=database_ready),
    )
