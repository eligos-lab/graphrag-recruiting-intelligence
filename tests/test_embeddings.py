import json
from collections.abc import Sequence

import httpx
import pytest

from app.llm.providers.openai import OpenAIEmbeddingProvider
from app.services.embeddings import EmbeddingService, EmbeddingValidationError


class FakeEmbeddingProvider:
    def __init__(self, dimension: int, vectors: list[list[float]]) -> None:
        self._dimension = dimension
        self.vectors = vectors
        self.calls: list[list[str]] = []

    @property
    def model(self) -> str:
        return "test-embedding-model"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        start = sum(len(call) for call in self.calls[:-1])
        return self.vectors[start : start + len(texts)]


async def test_embedding_service_batches_and_validates_vectors() -> None:
    provider = FakeEmbeddingProvider(
        dimension=3,
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    )
    service = EmbeddingService(provider, expected_dimension=3, batch_size=2)

    embeddings = await service.embed(["one", "two", "three"])

    assert embeddings == provider.vectors
    assert provider.calls == [["one", "two"], ["three"]]


@pytest.mark.parametrize(
    "vectors",
    [
        [[1.0, 2.0]],
        [[1.0, float("nan"), 3.0]],
    ],
)
async def test_embedding_service_rejects_invalid_vectors(vectors: list[list[float]]) -> None:
    service = EmbeddingService(
        FakeEmbeddingProvider(dimension=3, vectors=vectors),
        expected_dimension=3,
        batch_size=10,
    )

    with pytest.raises(EmbeddingValidationError):
        await service.embed(["text"])


async def test_openai_adapter_uses_documented_embeddings_contract() -> None:
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "text-embedding-3-small",
                "data": [
                    {"object": "embedding", "index": 1, "embedding": [0.0, 1.0]},
                    {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]},
                ],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIEmbeddingProvider(
            api_key="test-key",
            model="text-embedding-3-small",
            dimension=2,
            client=client,
        )
        embeddings = await provider.embed(["first", "second"])

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert captured_request is not None
    body = json.loads(captured_request.content)
    assert body == {
        "input": ["first", "second"],
        "model": "text-embedding-3-small",
        "dimensions": 2,
        "encoding_format": "float",
    }
