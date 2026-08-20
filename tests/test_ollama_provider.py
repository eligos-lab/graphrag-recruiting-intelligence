import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.llm.providers.ollama import OllamaEmbeddingProvider, OllamaLanguageModelProvider


class ExtractedValue(BaseModel):
    name: str
    score: int


@pytest.mark.asyncio
async def test_ollama_embedding_adapter_uses_local_embed_contract() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen3-embedding:0.6b",
                "embeddings": [[1.0, 0.0], [0.0, 1.0]],
                "prompt_eval_count": 4,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaEmbeddingProvider(
            model="qwen3-embedding:0.6b",
            dimension=2,
            client=client,
        )
        embeddings = await provider.embed(["first", "second"])

    assert embeddings == [[1.0, 0.0], [0.0, 1.0]]
    assert captured == {
        "model": "qwen3-embedding:0.6b",
        "input": ["first", "second"],
        "truncate": True,
    }


@pytest.mark.asyncio
async def test_ollama_chat_adapter_passes_json_schema_and_validates_output() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "qwen3:4b",
                "message": {"role": "assistant", "content": '{"name":"Ada","score":9}'},
                "done": True,
                "prompt_eval_count": 20,
                "eval_count": 8,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaLanguageModelProvider(model="qwen3:4b", client=client)
        result = await provider.structured_output(
            instructions="Extract a value",
            prompt="Ada scored 9",
            response_model=ExtractedValue,
        )

    assert result == ExtractedValue(name="Ada", score=9)
    assert captured["format"] == ExtractedValue.model_json_schema()
    assert captured["stream"] is False
    assert captured["think"] is False
    assert captured["options"] == {"temperature": 0}
