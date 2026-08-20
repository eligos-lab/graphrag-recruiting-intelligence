import json

import httpx
from pydantic import BaseModel, ConfigDict

from app.llm.providers.openai_responses import OpenAIResponsesProvider


class ParsedResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    skills: list[str] = []


async def test_openai_responses_adapter_uses_strict_json_schema() -> None:
    captured_request: httpx.Request | None = None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"role":"backend engineer","skills":["Kafka"]}',
                            }
                        ],
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIResponsesProvider(
            api_key="test-key",
            model="test-model",
            client=client,
        )
        parsed = await provider.structured_output(
            instructions="Parse intent",
            prompt="Find a backend engineer with Kafka",
            response_model=ParsedResult,
        )

    assert parsed.skills == ["Kafka"]
    assert captured_request is not None
    body = json.loads(captured_request.content)
    assert body["store"] is False
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    schema = body["text"]["format"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["role", "skills"]
    assert "default" not in json.dumps(schema)


async def test_openai_responses_adapter_extracts_plain_text() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "Grounded answer"}],
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIResponsesProvider(
            api_key="test-key",
            model="test-model",
            client=client,
        )
        answer = await provider.generate(instructions="Use evidence", prompt="Evidence: ...")

    assert answer == "Grounded answer"
