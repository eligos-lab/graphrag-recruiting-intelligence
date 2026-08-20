import logging
from collections.abc import Sequence

import httpx
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class EmbeddingUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = 0
    total_tokens: int = 0


class EmbeddingData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    embedding: list[float]
    index: int


class EmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[EmbeddingData]
    model: str
    usage: EmbeddingUsage | None = None


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = await self._client.post(
            self._endpoint,
            json={
                "input": list(texts),
                "model": self.model,
                "dimensions": self.dimension,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()
        payload = EmbeddingResponse.model_validate(response.json())
        if payload.usage is not None:
            logger.info(
                "Embedding call completed",
                extra={
                    "llm_model": payload.model,
                    "input_count": len(texts),
                    "prompt_tokens": payload.usage.prompt_tokens,
                    "total_tokens": payload.usage.total_tokens,
                },
            )
        ordered = sorted(payload.data, key=lambda item: item.index)
        return [item.embedding for item in ordered]

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "OpenAIEmbeddingProvider":
        return self

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object,
    ) -> None:
        await self.close()
