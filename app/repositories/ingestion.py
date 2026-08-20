from collections.abc import Iterable
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import (
    CompanyModel,
    DomainModel,
    PersonModel,
    ProjectModel,
    RawDocumentModel,
    SkillAliasModel,
    SkillModel,
    TechnologyModel,
    UniversityModel,
)
from app.ingestion.checksum import document_checksum
from app.ingestion.normalization import EntityNameNormalizer, normalize_name, normalized_identity
from app.ingestion.results import PersistOutcome
from app.ingestion.schemas import CanonicalResume, SourceDocument


class HasId(Protocol):
    id: UUID


ModelWithId = TypeVar("ModelWithId", bound=HasId)


class IngestionRepository:
    def __init__(
        self,
        session: AsyncSession,
        normalizer: EntityNameNormalizer | None = None,
    ) -> None:
        self.session = session
        self.normalizer = normalizer or EntityNameNormalizer()

    async def persist(
        self,
        document: SourceDocument,
        resume: CanonicalResume,
    ) -> PersistOutcome:
        checksum = document_checksum(document.raw_text)
        raw_document = await self._raw_document(document.source, document.external_id)

        if (
            raw_document is not None
            and raw_document.checksum == checksum
            and raw_document.person_id
        ):
            return PersistOutcome.UNCHANGED

        duplicate = await self._raw_document_by_checksum(checksum)
        if duplicate is not None and (raw_document is None or duplicate.id != raw_document.id):
            return PersistOutcome.DUPLICATE

        outcome = PersistOutcome.CREATED
        if raw_document is None:
            raw_document = RawDocumentModel(
                source=document.source,
                external_id=document.external_id,
                document_type=document.document_type.value,
                raw_text=document.raw_text,
                document_metadata=document.metadata,
                checksum=checksum,
            )
            self.session.add(raw_document)
            await self.session.flush()
        else:
            outcome = PersistOutcome.UPDATED
            raw_document.document_type = document.document_type.value
            raw_document.raw_text = document.raw_text
            raw_document.document_metadata = document.metadata
            raw_document.checksum = checksum

        person = await self._resolve_person(raw_document, resume)
        self._update_person(person, resume)
        await self._merge_resume_entities(person, resume)
        raw_document.person = person
        await self.session.flush()
        return outcome

    async def _raw_document(self, source: str, external_id: str) -> RawDocumentModel | None:
        raw_document: RawDocumentModel | None = await self.session.scalar(
            select(RawDocumentModel).where(
                RawDocumentModel.source == source,
                RawDocumentModel.external_id == external_id,
            )
        )
        return raw_document

    async def _raw_document_by_checksum(self, checksum: str) -> RawDocumentModel | None:
        raw_document: RawDocumentModel | None = await self.session.scalar(
            select(RawDocumentModel).where(RawDocumentModel.checksum == checksum)
        )
        return raw_document

    async def _resolve_person(
        self,
        raw_document: RawDocumentModel,
        resume: CanonicalResume,
    ) -> PersonModel:
        if raw_document.person_id is not None:
            existing = await self.session.get(PersonModel, raw_document.person_id)
            if existing is not None:
                return existing

        by_source = await self.session.scalar(
            select(PersonModel).where(
                PersonModel.source == resume.source,
                PersonModel.source_id == resume.external_id,
            )
        )
        if by_source is not None:
            return by_source

        identity = normalized_identity(resume.full_name, resume.country)
        if identity is not None:
            matches = list(
                await self.session.scalars(
                    select(PersonModel).where(PersonModel.normalized_identity == identity).limit(2)
                )
            )
            if len(matches) == 1:
                return matches[0]

        person = PersonModel(
            full_name=resume.full_name,
            location=resume.location,
            country=resume.country,
            current_title=resume.current_title,
            years_experience=resume.years_experience,
            summary=resume.summary,
            source=resume.source,
            source_id=resume.external_id,
            normalized_identity=identity,
            companies=[],
            skills=[],
            technologies=[],
            projects=[],
            universities=[],
            domains=[],
        )
        self.session.add(person)
        await self.session.flush()
        return person

    @staticmethod
    def _update_person(person: PersonModel, resume: CanonicalResume) -> None:
        person.full_name = resume.full_name
        person.normalized_identity = normalized_identity(resume.full_name, resume.country)
        for attribute in (
            "location",
            "country",
            "current_title",
            "years_experience",
            "summary",
        ):
            value = getattr(resume, attribute)
            if value is not None:
                setattr(person, attribute, value)

    async def _merge_resume_entities(
        self,
        person: PersonModel,
        resume: CanonicalResume,
    ) -> None:
        for skill_name in self._unique_non_empty(resume.skills):
            self._append_by_id(person.skills, await self._skill(skill_name))

        technology_names = list(resume.technologies)
        technology_names.extend(
            technology for experience in resume.experience for technology in experience.technologies
        )
        technology_names.extend(
            technology for project in resume.projects for technology in project.technologies
        )
        for technology_name in self._unique_non_empty(technology_names):
            self._append_by_id(
                person.technologies,
                await self._technology(technology_name),
            )

        domain_names = list(resume.domains)
        domain_names.extend(
            domain for experience in resume.experience for domain in experience.domains
        )
        domain_names.extend(domain for project in resume.projects for domain in project.domains)
        for domain_name in self._unique_non_empty(domain_names):
            self._append_by_id(person.domains, await self._domain(domain_name))

        for experience in resume.experience:
            company = await self._company(experience.company, None)
            self._append_by_id(person.companies, company)
            for domain_name in self._unique_non_empty(experience.domains):
                self._append_by_id(company.domains, await self._domain(domain_name))

        for education in resume.education:
            university = await self._university(education.university, education.country)
            self._append_by_id(person.universities, university)

        for project_item in resume.projects:
            project = await self._project(project_item.name, project_item.description)
            self._append_by_id(person.projects, project)
            for technology_name in self._unique_non_empty(project_item.technologies):
                self._append_by_id(
                    project.technologies,
                    await self._technology(technology_name),
                )
            for domain_name in self._unique_non_empty(project_item.domains):
                self._append_by_id(project.domains, await self._domain(domain_name))

    async def _skill(self, value: str) -> SkillModel:
        entity_name = self.normalizer.canonicalize(value)
        alias = await self.session.get(SkillAliasModel, entity_name.normalized_alias)
        if alias is not None:
            skill = await self.session.get(SkillModel, alias.skill_id)
            if skill is not None:
                return skill

        skill = await self.session.scalar(
            select(SkillModel).where(SkillModel.normalized_name == entity_name.normalized_name)
        )
        if skill is None:
            skill = SkillModel(
                name=entity_name.canonical_name,
                normalized_name=entity_name.normalized_name,
            )
            self.session.add(skill)
            await self.session.flush()

        self.session.add(SkillAliasModel(alias=entity_name.normalized_alias, skill_id=skill.id))
        await self.session.flush()
        return skill

    async def _technology(self, value: str) -> TechnologyModel:
        entity_name = self.normalizer.canonicalize(value)
        technology = await self.session.scalar(
            select(TechnologyModel).where(
                TechnologyModel.normalized_name == entity_name.normalized_name
            )
        )
        if technology is None:
            technology = TechnologyModel(
                name=entity_name.canonical_name,
                normalized_name=entity_name.normalized_name,
            )
            self.session.add(technology)
            await self.session.flush()
        return technology

    async def _domain(self, value: str) -> DomainModel:
        entity_name = self.normalizer.canonicalize(value)
        domain = await self.session.scalar(
            select(DomainModel).where(DomainModel.normalized_name == entity_name.normalized_name)
        )
        if domain is None:
            domain = DomainModel(
                name=entity_name.canonical_name,
                normalized_name=entity_name.normalized_name,
            )
            self.session.add(domain)
            await self.session.flush()
        return domain

    async def _company(self, value: str, country: str | None) -> CompanyModel:
        entity_name = self.normalizer.canonicalize(value)
        country_condition = (
            CompanyModel.country == country
            if country is not None
            else CompanyModel.country.is_(None)
        )
        company = await self.session.scalar(
            select(CompanyModel).where(
                CompanyModel.normalized_name == entity_name.normalized_name,
                country_condition,
            )
        )
        if company is None:
            company = CompanyModel(
                name=entity_name.canonical_name,
                normalized_name=entity_name.normalized_name,
                country=country,
                domains=[],
            )
            self.session.add(company)
            await self.session.flush()
        return company

    async def _university(self, value: str, country: str | None) -> UniversityModel:
        entity_name = self.normalizer.canonicalize(value)
        country_condition = (
            UniversityModel.country == country
            if country is not None
            else UniversityModel.country.is_(None)
        )
        university = await self.session.scalar(
            select(UniversityModel).where(
                UniversityModel.normalized_name == entity_name.normalized_name,
                country_condition,
            )
        )
        if university is None:
            university = UniversityModel(
                name=entity_name.canonical_name,
                normalized_name=entity_name.normalized_name,
                country=country,
            )
            self.session.add(university)
            await self.session.flush()
        return university

    async def _project(self, value: str, description: str | None) -> ProjectModel:
        entity_name = self.normalizer.canonicalize(value)
        project = await self.session.scalar(
            select(ProjectModel).where(ProjectModel.normalized_name == entity_name.normalized_name)
        )
        if project is None:
            project = ProjectModel(
                name=entity_name.canonical_name,
                normalized_name=entity_name.normalized_name,
                description=description,
                technologies=[],
                domains=[],
            )
            self.session.add(project)
            await self.session.flush()
        elif project.description is None and description is not None:
            project.description = description
        return project

    def _unique_non_empty(self, values: Iterable[str]) -> list[str]:
        unique_values: dict[str, str] = {}
        for value in values:
            normalized = normalize_name(value)
            if normalized:
                unique_values.setdefault(normalized, value)
        return list(unique_values.values())

    @staticmethod
    def _append_by_id(
        collection: list[ModelWithId],
        entity: ModelWithId,
    ) -> None:
        if all(existing.id != entity.id for existing in collection):
            collection.append(entity)
