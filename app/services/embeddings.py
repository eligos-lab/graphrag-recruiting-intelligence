import math
from collections.abc import Sequence

from app.llm.protocols import EmbeddingProvider


class EmbeddingValidationError(ValueError):
    pass


class EmbeddingService:
    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        expected_dimension: int,
        batch_size: int,
    ) -> None:
        if provider.dimension != expected_dimension:
            raise EmbeddingValidationError(
                f"Provider dimension {provider.dimension} does not match "
                f"configured dimension {expected_dimension}"
            )
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.provider = provider
        self.expected_dimension = expected_dimension
        self.batch_size = batch_size

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if any(not text.strip() for text in texts):
            raise EmbeddingValidationError("Embedding inputs cannot be empty")

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            batch_embeddings = await self.provider.embed(batch)
            if len(batch_embeddings) != len(batch):
                raise EmbeddingValidationError(
                    f"Provider returned {len(batch_embeddings)} vectors for {len(batch)} inputs"
                )
            for embedding in batch_embeddings:
                self._validate_vector(embedding)
            embeddings.extend(batch_embeddings)
        return embeddings

    def _validate_vector(self, embedding: Sequence[float]) -> None:
        if len(embedding) != self.expected_dimension:
            raise EmbeddingValidationError(
                f"Expected vector dimension {self.expected_dimension}, got {len(embedding)}"
            )
        if not all(math.isfinite(value) for value in embedding):
            raise EmbeddingValidationError("Embedding contains a non-finite value")
