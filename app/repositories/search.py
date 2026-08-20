from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    CompanyModel,
    DocumentChunkModel,
    DomainModel,
    PersonModel,
    ProjectModel,
    SkillModel,
    TechnologyModel,
)
from app.ingestion.normalization import EntityNameNormalizer, normalize_name
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import (
    CandidateEvidence,
    CandidateProfile,
    EvidenceSource,
)


class SqlAlchemyStructuredSearchRepository:
    def __init__(
        self,
        session: AsyncSession,
        normalizer: EntityNameNormalizer | None = None,
    ) -> None:
        self.session = session
        self.normalizer = normalizer or EntityNameNormalizer()

    async def filter_ids(self, intent: CandidateSearchIntent, *, limit: int) -> set[UUID]:
        statement = select(PersonModel.id)
        if intent.role:
            statement = statement.where(
                func.lower(PersonModel.current_title).contains(intent.role.casefold())
            )
        if intent.seniority:
            statement = statement.where(
                func.lower(PersonModel.current_title).contains(intent.seniority.casefold())
            )
        if intent.location.country:
            statement = statement.where(
                func.lower(PersonModel.country) == intent.location.country.casefold()
            )
        if intent.location.city:
            statement = statement.where(
                func.lower(PersonModel.location).contains(intent.location.city.casefold())
            )
        if intent.min_years_experience is not None:
            statement = statement.where(PersonModel.years_experience >= intent.min_years_experience)

        for skill in self._canonical_names(intent.required_skills):
            statement = statement.where(PersonModel.skills.any(SkillModel.normalized_name == skill))
        for technology in self._canonical_names(intent.required_technologies):
            statement = statement.where(
                PersonModel.technologies.any(TechnologyModel.normalized_name == technology)
            )
        for domain in self._normalized_names(intent.required_domains):
            statement = statement.where(
                PersonModel.domains.any(DomainModel.normalized_name == domain)
            )
        for company in self._normalized_names(intent.companies):
            statement = statement.where(
                PersonModel.companies.any(CompanyModel.normalized_name == company)
            )
        for project in self._normalized_names(intent.projects):
            statement = statement.where(
                PersonModel.projects.any(ProjectModel.normalized_name == project)
            )

        return set(await self.session.scalars(statement.order_by(PersonModel.id).limit(limit)))

    async def profiles(self, person_ids: set[UUID]) -> dict[UUID, CandidateProfile]:
        if not person_ids:
            return {}
        people = list(
            await self.session.scalars(select(PersonModel).where(PersonModel.id.in_(person_ids)))
        )
        return {
            person.id: CandidateProfile(
                person_id=person.id,
                full_name=person.full_name,
                location=person.location,
                country=person.country,
                current_title=person.current_title,
                years_experience=person.years_experience,
                summary=person.summary,
                skills=sorted(skill.name for skill in person.skills),
                technologies=sorted(technology.name for technology in person.technologies),
                domains=sorted(domain.name for domain in person.domains),
                companies=sorted(company.name for company in person.companies),
                projects=sorted(project.name for project in person.projects),
            )
            for person in people
        }

    async def evidence(
        self,
        person_ids: set[UUID],
    ) -> dict[UUID, list[CandidateEvidence]]:
        result: dict[UUID, list[CandidateEvidence]] = {person_id: [] for person_id in person_ids}
        if not person_ids:
            return result
        chunks = list(
            await self.session.scalars(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.person_id.in_(person_ids))
                .order_by(DocumentChunkModel.person_id, DocumentChunkModel.ordinal)
            )
        )
        for chunk in chunks:
            if len(result[chunk.person_id]) >= 5:
                continue
            result[chunk.person_id].append(
                CandidateEvidence(
                    person_id=chunk.person_id,
                    chunk_id=chunk.id,
                    source=EvidenceSource.STRUCTURED,
                    content=chunk.content,
                    score=1,
                    metadata=chunk.chunk_metadata,
                )
            )
        return result

    def _canonical_names(self, values: Sequence[str]) -> list[str]:
        return [self.normalizer.canonicalize(value).normalized_name for value in values]

    @staticmethod
    def _normalized_names(values: Sequence[str]) -> list[str]:
        return [normalize_name(value) for value in values]


class PgVectorSearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(
        self,
        embedding: Sequence[float],
        *,
        candidate_ids: set[UUID] | None,
        limit: int,
    ) -> list[CandidateEvidence]:
        if candidate_ids == set():
            return []
        distance = DocumentChunkModel.embedding.cosine_distance(list(embedding)).label("distance")
        statement = select(DocumentChunkModel, distance)
        if candidate_ids is not None:
            statement = statement.where(DocumentChunkModel.person_id.in_(candidate_ids))
        rows = (await self.session.execute(statement.order_by(distance).limit(limit))).all()
        return [
            CandidateEvidence(
                person_id=chunk.person_id,
                chunk_id=chunk.id,
                source=EvidenceSource.VECTOR,
                content=chunk.content,
                score=max(0.0, min(1.0, 1.0 - float(row_distance))),
                metadata=chunk.chunk_metadata,
            )
            for chunk, row_distance in rows
        ]
