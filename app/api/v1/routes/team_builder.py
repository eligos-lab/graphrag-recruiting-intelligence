from fastapi import APIRouter

from app.api.dependencies import SearchServiceDependency
from app.team_builder.agent import TeamBuilderAgent
from app.team_builder.models import TeamBuilderRequest, TeamBuildResponse

router = APIRouter()


@router.post("", response_model=TeamBuildResponse)
async def build_team(
    request: TeamBuilderRequest,
    search_service: SearchServiceDependency,
) -> TeamBuildResponse:
    return await TeamBuilderAgent(search_service.retriever).build(request)
