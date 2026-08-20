from fastapi import APIRouter

from app.api.dependencies import SearchServiceDependency
from app.schemas.search import SearchRequest, SearchResponse

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def search_candidates(
    request: SearchRequest,
    search_service: SearchServiceDependency,
) -> SearchResponse:
    result = await search_service.search(
        request.query,
        limit=request.limit,
        generate_answer=request.generate_answer,
    )
    return SearchResponse.model_validate(result.model_dump())
