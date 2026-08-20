import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ingestion.checksum import document_checksum
from app.ingestion.normalization import normalize_name
from app.ingestion.schemas import CanonicalResume

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
ChunkMetadataValue = str | int | float | bool | None


class ChunkSection(StrEnum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    PROJECT = "project"
    EDUCATION = "education"
    SKILLS = "skills"


class ResumeChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    person_id: UUID
    document_id: UUID
    section: ChunkSection
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1)
    content_checksum: str = Field(min_length=64, max_length=64)
    metadata: dict[str, ChunkMetadataValue]


class ResumeChunker:
    def __init__(self, max_characters: int = 2_000) -> None:
        if max_characters < 200:
            raise ValueError("max_characters must be at least 200")
        self.max_characters = max_characters

    def chunk(
        self,
        resume: CanonicalResume,
        *,
        person_id: UUID,
        document_id: UUID,
        company_ids: Mapping[str, UUID] | None = None,
    ) -> list[ResumeChunk]:
        company_ids = company_ids or {}
        drafts: list[tuple[ChunkSection, str, dict[str, ChunkMetadataValue]]] = []

        summary_blocks = self._non_empty(
            f"Candidate: {resume.full_name}",
            self._label("Current title", resume.current_title),
            self._label("Location", resume.location),
            self._label("Country", resume.country),
            self._label("Years of experience", resume.years_experience),
            resume.summary,
        )
        drafts.extend(
            self._section_drafts(
                ChunkSection.SUMMARY,
                "SUMMARY",
                summary_blocks,
                self._base_metadata(resume, person_id, document_id, ChunkSection.SUMMARY),
            )
        )

        for experience in resume.experience:
            metadata = self._base_metadata(resume, person_id, document_id, ChunkSection.EXPERIENCE)
            metadata["company_name"] = experience.company
            company_id = company_ids.get(normalize_name(experience.company))
            if company_id is not None:
                metadata["company_id"] = str(company_id)
            drafts.extend(
                self._section_drafts(
                    ChunkSection.EXPERIENCE,
                    f"EXPERIENCE: {experience.company}",
                    self._non_empty(
                        self._label("Title", experience.title),
                        self._date_range(experience.start_date, experience.end_date),
                        experience.description,
                        self._list_label("Domains", experience.domains),
                        self._list_label("Technologies", experience.technologies),
                    ),
                    metadata,
                )
            )

        for project in resume.projects:
            metadata = self._base_metadata(resume, person_id, document_id, ChunkSection.PROJECT)
            metadata["project_name"] = project.name
            drafts.extend(
                self._section_drafts(
                    ChunkSection.PROJECT,
                    f"PROJECT: {project.name}",
                    self._non_empty(
                        project.description,
                        self._list_label("Domains", project.domains),
                        self._list_label("Technologies", project.technologies),
                    ),
                    metadata,
                )
            )

        for education in resume.education:
            metadata = self._base_metadata(resume, person_id, document_id, ChunkSection.EDUCATION)
            metadata["university_name"] = education.university
            drafts.extend(
                self._section_drafts(
                    ChunkSection.EDUCATION,
                    f"EDUCATION: {education.university}",
                    self._non_empty(
                        self._label("Country", education.country),
                        self._label("Degree", education.degree),
                        self._label("Field", education.field_of_study),
                    ),
                    metadata,
                )
            )

        skills_blocks = self._non_empty(
            self._list_label("Skills", resume.skills),
            self._list_label("Technologies", resume.technologies),
            self._list_label("Domains", resume.domains),
        )
        if skills_blocks:
            drafts.extend(
                self._section_drafts(
                    ChunkSection.SKILLS,
                    "SKILLS AND EXPERTISE",
                    skills_blocks,
                    self._base_metadata(resume, person_id, document_id, ChunkSection.SKILLS),
                )
            )

        return [
            ResumeChunk(
                person_id=person_id,
                document_id=document_id,
                section=section,
                ordinal=ordinal,
                content=content,
                content_checksum=document_checksum(content),
                metadata=metadata,
            )
            for ordinal, (section, content, metadata) in enumerate(drafts)
        ]

    def _section_drafts(
        self,
        section: ChunkSection,
        header: str,
        blocks: Sequence[str],
        metadata: dict[str, ChunkMetadataValue],
    ) -> list[tuple[ChunkSection, str, dict[str, ChunkMetadataValue]]]:
        contents = self._pack_blocks(header, blocks)
        return [
            (section, content, {**metadata, "section_part": part})
            for part, content in enumerate(contents)
        ]

    def _pack_blocks(self, header: str, blocks: Sequence[str]) -> list[str]:
        chunks: list[str] = []
        current = header
        available = max(self.max_characters - len(header) - 2, 1)
        for block in blocks:
            for piece in self._split_block(block, available):
                candidate = f"{current}\n\n{piece}"
                if len(candidate) <= self.max_characters:
                    current = candidate
                else:
                    chunks.append(current)
                    current = f"{header}\n\n{piece}"
        chunks.append(current)
        return chunks

    def _split_block(self, block: str, limit: int) -> list[str]:
        if len(block) <= limit:
            return [block]
        sentences = _SENTENCE_BOUNDARY.split(block)
        pieces: list[str] = []
        current = ""
        for sentence in sentences:
            if len(sentence) > limit:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(self._split_words(sentence, limit))
                continue
            candidate = f"{current} {sentence}".strip()
            if len(candidate) <= limit:
                current = candidate
            else:
                pieces.append(current)
                current = sentence
        if current:
            pieces.append(current)
        return pieces

    @staticmethod
    def _split_words(value: str, limit: int) -> list[str]:
        pieces: list[str] = []
        current = ""
        for word in value.split():
            while len(word) > limit:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.append(word[:limit])
                word = word[limit:]
            candidate = f"{current} {word}".strip()
            if len(candidate) <= limit:
                current = candidate
            else:
                pieces.append(current)
                current = word
        if current:
            pieces.append(current)
        return pieces

    @staticmethod
    def _base_metadata(
        resume: CanonicalResume,
        person_id: UUID,
        document_id: UUID,
        section: ChunkSection,
    ) -> dict[str, ChunkMetadataValue]:
        return {
            "person_id": str(person_id),
            "document_id": str(document_id),
            "section": section.value,
            "source": resume.source,
            "external_id": resume.external_id,
        }

    @staticmethod
    def _non_empty(*values: str | None) -> list[str]:
        return [value.strip() for value in values if value is not None and value.strip()]

    @staticmethod
    def _label(label: str, value: object | None) -> str | None:
        return f"{label}: {value}" if value is not None and str(value).strip() else None

    @staticmethod
    def _list_label(label: str, values: Sequence[str]) -> str | None:
        return f"{label}: {', '.join(values)}" if values else None

    @staticmethod
    def _date_range(start_date: str | None, end_date: str | None) -> str | None:
        if start_date is None and end_date is None:
            return None
        return f"Dates: {start_date or 'unknown'} — {end_date or 'present'}"
