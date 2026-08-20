from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.graph.models import PersonGraphSnapshot
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import CandidateEvidence, CandidateProfile, GraphPath


class StructuredSearchRepository(Protocol):
    async def filter_ids(self, intent: CandidateSearchIntent, *, limit: int) -> set[UUID]: ...

    async def profiles(self, person_ids: set[UUID]) -> dict[UUID, CandidateProfile]: ...

    async def evidence(self, person_ids: set[UUID]) -> dict[UUID, list[CandidateEvidence]]: ...


class VectorSearchRepository(Protocol):
    async def search(
        self,
        embedding: Sequence[float],
        *,
        candidate_ids: set[UUID] | None,
        limit: int,
    ) -> list[CandidateEvidence]: ...


class GraphSearchRepository(Protocol):
    async def sync_person(self, snapshot: PersonGraphSnapshot) -> None: ...

    async def search_ids(self, intent: CandidateSearchIntent, *, limit: int) -> set[UUID]: ...

    async def paths(
        self,
        person_ids: set[UUID],
        *,
        max_hops: int,
        limit: int,
    ) -> list[GraphPath]: ...

    async def close(self) -> None: ...
