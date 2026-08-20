from pydantic import BaseModel, Field

from app.graph.neo4j import Neo4jGraphRepository
from app.repositories.graph_snapshot import GraphSnapshotRepository


class GraphSyncError(BaseModel):
    person_id: str
    message: str


class GraphSyncReport(BaseModel):
    total: int = 0
    synced: int = 0
    failed: int = 0
    errors: list[GraphSyncError] = Field(default_factory=list)


class GraphSyncService:
    def __init__(
        self,
        snapshot_repository: GraphSnapshotRepository,
        graph_repository: "Neo4jGraphRepository",
    ) -> None:
        self.snapshot_repository = snapshot_repository
        self.graph_repository = graph_repository

    async def sync(self, *, limit: int | None = None) -> GraphSyncReport:
        await self.graph_repository.ensure_schema()
        snapshots = await self.snapshot_repository.list_people(limit=limit)
        report = GraphSyncReport(total=len(snapshots))
        for snapshot in snapshots:
            try:
                await self.graph_repository.sync_person(snapshot)
                report.synced += 1
            except Exception as error:
                report.failed += 1
                report.errors.append(GraphSyncError(person_id=str(snapshot.id), message=str(error)))
        return report
