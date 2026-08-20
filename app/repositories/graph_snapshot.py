from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.models import (
    GraphCompanySnapshot,
    GraphNodeSnapshot,
    GraphProjectSnapshot,
    PersonGraphSnapshot,
)
from app.infrastructure.database.models import DocumentChunkModel, PersonModel


class NamedEntityModel(Protocol):
    id: UUID
    name: str
    normalized_name: str


class GraphSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_people(
        self,
        *,
        person_ids: set[UUID] | None = None,
        limit: int | None = None,
    ) -> list[PersonGraphSnapshot]:
        statement = select(PersonModel).order_by(PersonModel.id)
        if person_ids is not None:
            if not person_ids:
                return []
            statement = statement.where(PersonModel.id.in_(person_ids))
        if limit is not None:
            statement = statement.limit(limit)
        people = list(await self.session.scalars(statement))
        evidence = await self._evidence({person.id for person in people})
        return [self._snapshot(person, evidence.get(person.id, [])) for person in people]

    async def _evidence(self, person_ids: set[UUID]) -> dict[UUID, list[UUID]]:
        result: dict[UUID, list[UUID]] = {person_id: [] for person_id in person_ids}
        if not person_ids:
            return result
        rows = await self.session.execute(
            select(DocumentChunkModel.person_id, DocumentChunkModel.id).where(
                DocumentChunkModel.person_id.in_(person_ids)
            )
        )
        for person_id, chunk_id in rows:
            result[person_id].append(chunk_id)
        return result

    @staticmethod
    def _node(
        entity: NamedEntityModel,
        evidence_ids: list[UUID],
    ) -> GraphNodeSnapshot:
        return GraphNodeSnapshot(
            id=entity.id,
            name=entity.name,
            normalized_name=entity.normalized_name,
            evidence_ids=evidence_ids,
        )

    @classmethod
    def _snapshot(
        cls,
        person: PersonModel,
        evidence_ids: list[UUID],
    ) -> PersonGraphSnapshot:
        return PersonGraphSnapshot(
            id=person.id,
            full_name=person.full_name,
            country=person.country,
            current_title=person.current_title,
            evidence_ids=evidence_ids,
            companies=[
                GraphCompanySnapshot(
                    **cls._node(company, evidence_ids).model_dump(),
                    domains=[cls._node(domain, evidence_ids) for domain in company.domains],
                )
                for company in person.companies
            ],
            skills=[cls._node(skill, evidence_ids) for skill in person.skills],
            technologies=[cls._node(item, evidence_ids) for item in person.technologies],
            projects=[
                GraphProjectSnapshot(
                    **cls._node(project, evidence_ids).model_dump(),
                    technologies=[
                        cls._node(technology, evidence_ids) for technology in project.technologies
                    ],
                    domains=[cls._node(domain, evidence_ids) for domain in project.domains],
                )
                for project in person.projects
            ],
            universities=[cls._node(item, evidence_ids) for item in person.universities],
            domains=[cls._node(item, evidence_ids) for item in person.domains],
        )
