import logging
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.llm.protocols import StructuredModel

logger = logging.getLogger(__name__)


class ResponseContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    text: str | None = None


class ResponseOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    content: list[ResponseContent] = Field(default_factory=list)


class ResponseUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ResponsesPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    output: list[ResponseOutput]
    usage: ResponseUsage | None = None


class OpenAIResponsesProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 90.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._model = model
        self._endpoint = f"{base_url.rstrip('/')}/responses"
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, *, instructions: str, prompt: str) -> str:
        payload = await self._request(
            {
                "model": self.model,
                "instructions": instructions,
                "input": prompt,
                "store": False,
            }
        )
        return self._output_text(payload)

    async def structured_output(
        self,
        *,
        instructions: str,
        prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredModel:
        schema = self._strict_schema(response_model.model_json_schema())
        payload = await self._request(
            {
                "model": self.model,
                "instructions": instructions,
                "input": prompt,
                "store": False,
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": response_model.__name__,
                        "schema": schema,
                        "strict": True,
                    }
                },
            }
        )
        return response_model.model_validate_json(self._output_text(payload))

    async def _request(self, body: dict[str, Any]) -> ResponsesPayload:
        response = await self._client.post(self._endpoint, json=body)
        response.raise_for_status()
        payload = ResponsesPayload.model_validate(response.json())
        if payload.status != "completed":
            raise RuntimeError(f"OpenAI response did not complete: {payload.status}")
        if payload.usage is not None:
            logger.info(
                "LLM response completed",
                extra={
                    "llm_model": self.model,
                    "input_tokens": payload.usage.input_tokens,
                    "output_tokens": payload.usage.output_tokens,
                    "total_tokens": payload.usage.total_tokens,
                },
            )
        return payload

    @staticmethod
    def _output_text(payload: ResponsesPayload) -> str:
        for output in payload.output:
            if output.type != "message":
                continue
            for content in output.content:
                if content.type == "output_text" and content.text is not None:
                    return content.text
        raise ValueError("OpenAI response contains no output_text")

    @classmethod
    def _strict_schema(cls, value: Any) -> Any:
        if isinstance(value, dict):
            normalized = {
                key: cls._strict_schema(item) for key, item in value.items() if key != "default"
            }
            if normalized.get("type") == "object" or "properties" in normalized:
                properties = normalized.get("properties", {})
                normalized["additionalProperties"] = False
                normalized["required"] = list(properties)
            return normalized
        if isinstance(value, list):
            return [cls._strict_schema(item) for item in value]
        return value

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "OpenAIResponsesProvider":
        return self

    async def __aexit__(
        self,
        _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: object,
    ) -> None:
        await self.close()
