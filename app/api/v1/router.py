from fastapi import APIRouter

from app.api.v1.routes.candidates import router as candidates_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.ingestion import router as ingestion_router
from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.team_builder import router as team_builder_router

router = APIRouter()
router.include_router(candidates_router, prefix="/candidates", tags=["candidates"])
router.include_router(health_router, prefix="/health", tags=["health"])
router.include_router(ingestion_router, prefix="/ingestion/jobs", tags=["ingestion"])
router.include_router(search_router, prefix="/search", tags=["search"])
router.include_router(team_builder_router, prefix="/team-builder", tags=["team-builder"])
