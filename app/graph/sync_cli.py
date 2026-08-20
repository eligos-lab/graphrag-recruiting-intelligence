import argparse
import asyncio

from app.config import get_settings
from app.graph.neo4j import Neo4jGraphRepository
from app.graph.sync import GraphSyncService
from app.infrastructure.database.session import async_session_factory
from app.repositories.graph_snapshot import GraphSnapshotRepository


async def sync_graph(limit: int | None = None) -> int:
    settings = get_settings()
    graph_repository = Neo4jGraphRepository.connect(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )
    try:
        async with async_session_factory() as session:
            report = await GraphSyncService(
                GraphSnapshotRepository(session),
                graph_repository,
            ).sync(limit=limit)
    finally:
        await graph_repository.close()
    print(report.model_dump_json(indent=2))
    return 1 if report.failed else 0


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description="Synchronize relational candidate facts into Neo4j"
    )
    argument_parser.add_argument("--limit", type=int)
    arguments = argument_parser.parse_args()
    if arguments.limit is not None and arguments.limit < 1:
        argument_parser.error("--limit must be positive")
    raise SystemExit(asyncio.run(sync_graph(arguments.limit)))


if __name__ == "__main__":
    main()
