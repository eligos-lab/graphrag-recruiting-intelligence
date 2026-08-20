from pydantic import BaseModel, Field

from app.services.search import SearchExecutionResult


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=4_000)
    limit: int = Field(default=20, ge=1, le=100)
    generate_answer: bool = True


class SearchResponse(SearchExecutionResult):
    pass
