import argparse
import asyncio
import sys

from app.config import get_settings
from app.infrastructure.database.session import async_session_factory
from app.ingestion.chunking import ResumeChunker
from app.ingestion.embedding_pipeline import StructuredEmbeddingPipeline
from app.llm.providers.openai import OpenAIEmbeddingProvider
from app.services.embeddings import EmbeddingService


async def embed_documents(limit: int | None = None) -> int:
    settings = get_settings()
    api_key = (
        settings.embedding_api_key.get_secret_value().strip()
        if settings.embedding_api_key is not None
        else ""
    )
    if not api_key:
        print(
            "error: GRAPHRAG_EMBEDDING_API_KEY is required to generate embeddings",
            file=sys.stderr,
        )
        return 2

    async with OpenAIEmbeddingProvider(
        api_key=api_key,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        base_url=settings.embedding_base_url,
        timeout_seconds=settings.embedding_timeout_seconds,
    ) as provider:
        service = EmbeddingService(
            provider,
            expected_dimension=settings.embedding_dimension,
            batch_size=settings.embedding_batch_size,
        )
        pipeline = StructuredEmbeddingPipeline(
            service,
            chunker=ResumeChunker(settings.chunk_max_characters),
        )
        async with async_session_factory() as session:
            report = await pipeline.run(session, limit=limit)

    print(report.model_dump_json(indent=2))
    return 1 if report.failed else 0


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description="Create or refresh section-aware embeddings for structured resumes"
    )
    argument_parser.add_argument("--limit", type=int)
    arguments = argument_parser.parse_args()
    if arguments.limit is not None and arguments.limit < 1:
        argument_parser.error("--limit must be positive")
    raise SystemExit(asyncio.run(embed_documents(arguments.limit)))


if __name__ == "__main__":
    main()
