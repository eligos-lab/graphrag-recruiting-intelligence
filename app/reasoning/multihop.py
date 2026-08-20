from uuid import UUID

from pydantic import BaseModel, Field

from app.retrieval.models import CandidateReason, ClaimKind, GraphPath
from app.retrieval.protocols import GraphSearchRepository


class MultiHopResult(BaseModel):
    person_id: UUID
    max_hops: int = Field(ge=1, le=3)
    paths: list[GraphPath]
    facts: list[CandidateReason]


class MultiHopReasoner:
    def __init__(self, graph_repository: GraphSearchRepository) -> None:
        self.graph_repository = graph_repository

    async def explain(
        self,
        person_id: UUID,
        *,
        max_hops: int,
        limit: int = 100,
    ) -> MultiHopResult:
        if not 1 <= max_hops <= 3:
            raise ValueError("max_hops must be between 1 and 3")
        paths = await self.graph_repository.paths(
            {person_id},
            max_hops=max_hops,
            limit=limit,
        )
        facts = [
            CandidateReason(
                claim=" → ".join(path.nodes),
                kind=ClaimKind.FACT,
                evidence_ids=path.evidence_ids,
            )
            for path in paths
            if path.evidence_ids
        ]
        return MultiHopResult(
            person_id=person_id,
            max_hops=max_hops,
            paths=paths,
            facts=facts,
        )
