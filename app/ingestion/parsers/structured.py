import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.ingestion.schemas import (
    CanonicalResume,
    EducationItem,
    ExperienceItem,
    ProjectItem,
    SourceDocument,
)

_LIST_SEPARATOR = re.compile(r"\s*[;,|]\s*")


class StructuredFieldMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    full_name: str = "full_name"
    location: str = "location"
    country: str = "country"
    current_title: str = "current_title"
    years_experience: str = "years_experience"
    age: str = "age"
    summary: str = "summary"
    experience: str = "experience"
    skills: str = "skills"
    technologies: str = "technologies"
    education: str = "education"
    projects: str = "projects"
    domains: str = "domains"


class StructuredResumeParser:
    def __init__(self, mapping: StructuredFieldMapping | None = None) -> None:
        self.mapping = mapping or StructuredFieldMapping()

    def parse(self, document: SourceDocument) -> CanonicalResume:
        payload = document.payload
        full_name = self._string_value(payload, self.mapping.full_name, ("name", "candidate_name"))
        if full_name is None:
            raise ValueError(f"Resume {document.external_id} has no full name")

        return CanonicalResume(
            source=document.source,
            external_id=document.external_id,
            full_name=full_name,
            location=self._string_value(payload, self.mapping.location),
            country=self._string_value(payload, self.mapping.country),
            current_title=self._string_value(
                payload, self.mapping.current_title, ("title", "job_title")
            ),
            years_experience=self._float_value(payload, self.mapping.years_experience),
            age=self._integer_value(payload, self.mapping.age),
            summary=self._string_value(payload, self.mapping.summary, ("profile", "about")),
            experience=self._experience_items(self._value(payload, self.mapping.experience)),
            skills=self._string_list(self._value(payload, self.mapping.skills)),
            technologies=self._string_list(self._value(payload, self.mapping.technologies)),
            education=self._education_items(self._value(payload, self.mapping.education)),
            projects=self._project_items(self._value(payload, self.mapping.projects)),
            domains=self._string_list(self._value(payload, self.mapping.domains)),
        )

    def _value(self, payload: Mapping[str, Any], field_path: str) -> Any:
        current: Any = payload
        for part in field_path.split("."):
            if not isinstance(current, Mapping) or part not in current:
                return None
            current = current[part]
        return current

    def _string_value(
        self,
        payload: Mapping[str, Any],
        field_path: str,
        aliases: Iterable[str] = (),
    ) -> str | None:
        for candidate in (field_path, *aliases):
            value = self._value(payload, candidate)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    def _float_value(self, payload: Mapping[str, Any], field_path: str) -> float | None:
        value = self._value(payload, field_path)
        if value is None or not str(value).strip():
            return None
        return float(value)

    def _integer_value(self, payload: Mapping[str, Any], field_path: str) -> int | None:
        value = self._value(payload, field_path)
        if value is None or not str(value).strip():
            return None
        return int(value)

    def _structured_list(self, value: Any) -> list[Any]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list):
                    raise ValueError("Expected a JSON list")
                return parsed
        raise ValueError("Expected a list or a JSON-encoded list")

    def _string_list(self, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            values = value
        elif isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                values = self._structured_list(stripped)
            else:
                values = _LIST_SEPARATOR.split(stripped)
        else:
            values = [value]
        return [str(item).strip() for item in values if str(item).strip()]

    def _experience_items(self, value: Any) -> list[ExperienceItem]:
        items = self._structured_list(value)
        result: list[ExperienceItem] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise ValueError("Every experience item must be an object")
            company = self._first_string(item, "company", "company_name", "employer")
            if company is None:
                raise ValueError("Experience item has no company")
            result.append(
                ExperienceItem(
                    company=company,
                    title=self._first_string(item, "title", "role"),
                    start_date=self._first_string(item, "start_date", "start"),
                    end_date=self._first_string(item, "end_date", "end"),
                    description=self._first_string(item, "description", "summary"),
                    domains=self._string_list(item.get("domains")),
                    technologies=self._string_list(item.get("technologies")),
                )
            )
        return result

    def _education_items(self, value: Any) -> list[EducationItem]:
        items = self._structured_list(value)
        result: list[EducationItem] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise ValueError("Every education item must be an object")
            university = self._first_string(item, "university", "institution", "school")
            if university is None:
                raise ValueError("Education item has no university")
            result.append(
                EducationItem(
                    university=university,
                    country=self._first_string(item, "country"),
                    degree=self._first_string(item, "degree"),
                    field_of_study=self._first_string(item, "field_of_study", "field"),
                )
            )
        return result

    def _project_items(self, value: Any) -> list[ProjectItem]:
        items = self._structured_list(value)
        result: list[ProjectItem] = []
        for item in items:
            if not isinstance(item, Mapping):
                raise ValueError("Every project item must be an object")
            name = self._first_string(item, "name", "project_name")
            if name is None:
                raise ValueError("Project item has no name")
            result.append(
                ProjectItem(
                    name=name,
                    description=self._first_string(item, "description", "summary"),
                    technologies=self._string_list(item.get("technologies")),
                    domains=self._string_list(item.get("domains")),
                )
            )
        return result

    @staticmethod
    def _first_string(item: Mapping[str, Any], *names: str) -> str | None:
        for name in names:
            value = item.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None
