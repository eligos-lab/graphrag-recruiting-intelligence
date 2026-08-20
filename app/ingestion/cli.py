import argparse
import asyncio
from pathlib import Path

from app.infrastructure.database.session import async_session_factory
from app.ingestion.pipeline import StructuredIngestionPipeline
from app.ingestion.sources import BaseDataSource, CsvResumeSource, JsonResumeSource


def build_source(path: Path, source_name: str | None) -> BaseDataSource:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return CsvResumeSource(path, source_name=source_name)
    if suffix in {".json", ".jsonl"}:
        return JsonResumeSource(path, source_name=source_name)
    raise ValueError(f"Unsupported structured source format: {suffix}")


async def ingest_file(path: Path, source_name: str | None) -> int:
    source = build_source(path, source_name)
    async with async_session_factory() as session:
        report = await StructuredIngestionPipeline().ingest(source, session)
    print(report.model_dump_json(indent=2))
    return 1 if report.failed else 0


def main() -> None:
    argument_parser = argparse.ArgumentParser(description="Ingest a structured resume dataset")
    argument_parser.add_argument("path", type=Path)
    argument_parser.add_argument("--source-name")
    arguments = argument_parser.parse_args()
    raise SystemExit(asyncio.run(ingest_file(arguments.path, arguments.source_name)))


if __name__ == "__main__":
    main()
