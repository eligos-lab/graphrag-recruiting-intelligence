from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router as api_v1_router
from app.config import get_settings
from app.infrastructure.cache import redis_client
from app.infrastructure.database.session import engine
from app.infrastructure.graph import graph_repository
from app.security import SecurityMiddleware
from app.web import _WEB_ROOT, frontend


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await redis_client.aclose()
    await graph_repository.close()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    application.add_middleware(
        SecurityMiddleware,
        access_key=settings.api_access_key.get_secret_value() if settings.api_access_key else None,
        rate_limit=settings.api_rate_limit_per_minute,
    )
    application.include_router(api_v1_router, prefix="/api/v1")
    application.mount("/assets", StaticFiles(directory=_WEB_ROOT), name="assets")
    application.add_api_route("/", frontend, include_in_schema=False)
    return application


app = create_app()
