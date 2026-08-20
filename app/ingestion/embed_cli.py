import argparse
import asyncio
import sys

from app.config import get_settings
from app.infrastructure.database.session import async_session_factory
from app.ingestion.chunking import ResumeChunker
from app.ingestion.embedding_pipeline import StructuredEmbeddingPipeline
from app.llm.factory import ProviderConfigurationError, create_embedding_provider
from app.services.embeddings import EmbeddingService


async def embed_documents(limit: int | None = None) -> int:
    settings = get_settings()
    try:
        provider = create_embedding_provider(settings)
    except ProviderConfigurationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    async with provider:
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
