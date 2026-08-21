import re
import unicodedata
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s+")
_SPECIAL_TECH_NAMES = {
    ".net": "dotnet",
    "c#": "csharp",
    "c++": "cpp",
}

DEFAULT_ENTITY_ALIASES = {
    "питон": "Python",
    "python разработчик": "Python",
    "python разработчики": "Python",
    "кубернетес": "Kubernetes",
    "кафка": "Kafka",
    "линукс": "Linux",
    "mts": "МТС",  # noqa: RUF001
    "мтс": "МТС",  # noqa: RUF001
    "amazon web service": "Amazon Web Services",
    "amazon web services": "Amazon Web Services",
    "aws": "Amazon Web Services",
    "gcp": "Google Cloud Platform",
    "gnn": "Graph Neural Networks",
    "google cloud": "Google Cloud Platform",
    "google cloud platform": "Google Cloud Platform",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "postgres": "PostgreSQL",
    "postgre sql": "PostgreSQL",
    "postgresql": "PostgreSQL",
}


def normalize_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    for source, replacement in _SPECIAL_TECH_NAMES.items():
        normalized = normalized.replace(source, replacement)
    normalized = normalized.replace("&", " and ")
    normalized = "".join(
        character if not unicodedata.category(character).startswith(("P", "S")) else " "
        for character in normalized
    )
    return _WHITESPACE.sub(" ", normalized).strip()


@dataclass(frozen=True, slots=True)
class CanonicalEntityName:
    original_name: str
    normalized_alias: str
    canonical_name: str
    normalized_name: str


class EntityNameNormalizer:
    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        raw_aliases = aliases or DEFAULT_ENTITY_ALIASES
        self._aliases = {
            normalize_name(alias): canonical for alias, canonical in raw_aliases.items()
        }

    def canonicalize(self, value: str) -> CanonicalEntityName:
        stripped = value.strip()
        normalized_alias = normalize_name(stripped)
        canonical_name = self._aliases.get(normalized_alias, stripped)
        return CanonicalEntityName(
            original_name=stripped,
            normalized_alias=normalized_alias,
            canonical_name=canonical_name,
            normalized_name=normalize_name(canonical_name),
        )


def normalized_identity(full_name: str, country: str | None) -> str | None:
    normalized_country = normalize_name(country or "")
    if not normalized_country:
        return None
    return f"{normalize_name(full_name)}|{normalized_country}"
