import json
import logging
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from app.llm.protocols import StructuredModel

logger = logging.getLogger(__name__)


class OllamaMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    content: str


class OllamaChatResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    message: OllamaMessage
    done: bool
    prompt_eval_count: int = 0
    eval_count: int = 0


class OllamaEmbeddingResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    embeddings: list[list[float]]
    prompt_eval_count: int = 0


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        model: str,
        dimension: int,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 300.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._endpoint = f"{base_url.rstrip('/')}/api/embed"
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        response = await self._client.post(
            self._endpoint,
            json={"model": self.model, "input": list(texts), "truncate": True},
        )
        response.raise_for_status()
        payload = OllamaEmbeddingResponse.model_validate(response.json())
        logger.info(
            "Local embedding call completed",
            extra={
                "llm_model": payload.model,
                "input_count": len(texts),
                "prompt_tokens": payload.prompt_eval_count,
            },
        )
        return payload.embeddings

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "OllamaEmbeddingProvider":
        return self

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object,
    ) -> None:
        await self.close()


class OllamaLanguageModelProvider:
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 300.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._endpoint = f"{base_url.rstrip('/')}/api/chat"
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, *, instructions: str, prompt: str) -> str:
        payload = await self._request(instructions=instructions, prompt=prompt)
        return payload.message.content

    async def structured_output(
        self,
        *,
        instructions: str,
        prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredModel:
        schema = response_model.model_json_schema()
        schema_prompt = (
            f"{prompt}\n\nReturn only JSON matching this schema exactly:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        payload = await self._request(
            instructions=instructions,
            prompt=schema_prompt,
            response_format=schema,
        )
        return response_model.model_validate_json(payload.message.content)

    async def _request(
        self,
        *,
        instructions: str,
        prompt: str,
        response_format: dict[str, Any] | None = None,
    ) -> OllamaChatResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }
        if response_format is not None:
            body["format"] = response_format
        response = await self._client.post(self._endpoint, json=body)
        response.raise_for_status()
        payload = OllamaChatResponse.model_validate(response.json())
        if not payload.done:
            raise RuntimeError("Ollama response did not complete")
        logger.info(
            "Local LLM response completed",
            extra={
                "llm_model": payload.model,
                "input_tokens": payload.prompt_eval_count,
                "output_tokens": payload.eval_count,
                "total_tokens": payload.prompt_eval_count + payload.eval_count,
            },
        )
        return payload

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "OllamaLanguageModelProvider":
        return self

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object,
    ) -> None:
        await self.close()
