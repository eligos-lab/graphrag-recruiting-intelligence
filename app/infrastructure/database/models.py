from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Float, ForeignKey, String, Table, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin

DOCUMENT_METADATA_TYPE = JSON().with_variant(JSONB(), "postgresql")

person_companies = Table(
    "person_companies",
    Base.metadata,
    Column(
        "person_id",
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "company_id",
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
person_skills = Table(
    "person_skills",
    Base.metadata,
    Column(
        "person_id",
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        Uuid(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
person_technologies = Table(
    "person_technologies",
    Base.metadata,
    Column(
        "person_id",
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technology_id",
        Uuid(as_uuid=True),
        ForeignKey("technologies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
person_projects = Table(
    "person_projects",
    Base.metadata,
    Column(
        "person_id",
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "project_id",
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
person_universities = Table(
    "person_universities",
    Base.metadata,
    Column(
        "person_id",
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "university_id",
        Uuid(as_uuid=True),
        ForeignKey("universities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
person_domains = Table(
    "person_domains",
    Base.metadata,
    Column(
        "person_id",
        Uuid(as_uuid=True),
        ForeignKey("people.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "domain_id",
        Uuid(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
company_domains = Table(
    "company_domains",
    Base.metadata,
    Column(
        "company_id",
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "domain_id",
        Uuid(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
project_technologies = Table(
    "project_technologies",
    Base.metadata,
    Column(
        "project_id",
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technology_id",
        Uuid(as_uuid=True),
        ForeignKey("technologies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
project_domains = Table(
    "project_domains",
    Base.metadata,
    Column(
        "project_id",
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "domain_id",
        Uuid(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class PersonModel(TimestampMixin, Base):
    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_people_source_source_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100), index=True)
    current_title: Mapped[str | None] = mapped_column(String(255), index=True)
    years_experience: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[str] = mapped_column(String(255))
    normalized_identity: Mapped[str | None] = mapped_column(String(512), index=True)

    companies: Mapped[list[CompanyModel]] = relationship(
        secondary=person_companies, lazy="selectin"
    )
    skills: Mapped[list[SkillModel]] = relationship(secondary=person_skills, lazy="selectin")
    technologies: Mapped[list[TechnologyModel]] = relationship(
        secondary=person_technologies, lazy="selectin"
    )
    projects: Mapped[list[ProjectModel]] = relationship(secondary=person_projects, lazy="selectin")
    universities: Mapped[list[UniversityModel]] = relationship(
        secondary=person_universities, lazy="selectin"
    )
    domains: Mapped[list[DomainModel]] = relationship(secondary=person_domains, lazy="selectin")


class CompanyModel(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint(
            "normalized_name",
            "country",
            name="uq_companies_normalized_name_country",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    domains: Mapped[list[DomainModel]] = relationship(secondary=company_domains, lazy="selectin")


class SkillModel(TimestampMixin, Base):
    __tablename__ = "skills"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100))


class SkillAliasModel(Base):
    __tablename__ = "skill_aliases"

    alias: Mapped[str] = mapped_column(String(255), primary_key=True)
    skill_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), index=True
    )
    skill: Mapped[SkillModel] = relationship()


class TechnologyModel(TimestampMixin, Base):
    __tablename__ = "technologies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)


class ProjectModel(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[list[TechnologyModel]] = relationship(
        secondary=project_technologies, lazy="selectin"
    )
    domains: Mapped[list[DomainModel]] = relationship(secondary=project_domains, lazy="selectin")


class UniversityModel(TimestampMixin, Base):
    __tablename__ = "universities"
    __table_args__ = (
        UniqueConstraint(
            "normalized_name",
            "country",
            name="uq_universities_normalized_name_country",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str | None] = mapped_column(String(100))


class DomainModel(TimestampMixin, Base):
    __tablename__ = "domains"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)


class RawDocumentModel(TimestampMixin, Base):
    __tablename__ = "raw_documents"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_raw_documents_source_external_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    person_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[str] = mapped_column(String(100))
    external_id: Mapped[str] = mapped_column(String(255))
    document_type: Mapped[str] = mapped_column(String(50))
    raw_text: Mapped[str] = mapped_column(Text)
    document_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", DOCUMENT_METADATA_TYPE, default=dict
    )
    checksum: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    person: Mapped[PersonModel | None] = relationship()
