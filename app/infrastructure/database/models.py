from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import Column, Float, ForeignKey, String, Table, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin

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

    companies: Mapped[list[CompanyModel]] = relationship(secondary=person_companies)
    skills: Mapped[list[SkillModel]] = relationship(secondary=person_skills)
    technologies: Mapped[list[TechnologyModel]] = relationship(secondary=person_technologies)
    projects: Mapped[list[ProjectModel]] = relationship(secondary=person_projects)
    universities: Mapped[list[UniversityModel]] = relationship(secondary=person_universities)
    domains: Mapped[list[DomainModel]] = relationship(secondary=person_domains)


class CompanyModel(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("name", "country", name="uq_companies_name_country"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    industry: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    domains: Mapped[list[DomainModel]] = relationship(secondary=company_domains)


class SkillModel(TimestampMixin, Base):
    __tablename__ = "skills"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100))


class TechnologyModel(TimestampMixin, Base):
    __tablename__ = "technologies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)


class ProjectModel(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[list[TechnologyModel]] = relationship(secondary=project_technologies)
    domains: Mapped[list[DomainModel]] = relationship(secondary=project_domains)


class UniversityModel(TimestampMixin, Base):
    __tablename__ = "universities"
    __table_args__ = (UniqueConstraint("name", "country", name="uq_universities_name_country"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str | None] = mapped_column(String(100))


class DomainModel(TimestampMixin, Base):
    __tablename__ = "domains"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
