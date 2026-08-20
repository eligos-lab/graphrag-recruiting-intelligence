from collections.abc import Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class EmbeddingProvider(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class LanguageModelProvider(Protocol):
    @property
    def model(self) -> str: ...

    async def generate(self, *, instructions: str, prompt: str) -> str: ...

    async def structured_output(
        self,
        *,
        instructions: str,
        prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredModel: ...
