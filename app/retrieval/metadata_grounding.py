"""Ground free-form intent values against metadata that actually exists in the corpus."""

from dataclasses import dataclass
from difflib import SequenceMatcher

from app.ingestion.normalization import normalize_name
from app.retrieval.intent import CandidateSearchIntent, LocationIntent

_CITY_ALIASES = {
    "мск": "москва",
    "масква": "москва",
    "московия": "москва",
    "moscow": "москва",
    "спб": "санкт петербург",
    "питер": "санкт петербург",
    "петербург": "санкт петербург",
}

_COMPANY_ALIASES = {
    "вк": "vk",
    "вконтакте": "vk",
    "mts": "мтс",
}


@dataclass(frozen=True, slots=True)
class SearchVocabulary:
    cities: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    companies: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()

    def as_prompt_data(self) -> dict[str, tuple[str, ...]]:
        return {
            "cities": self.cities,
            "countries": self.countries,
            "companies": self.companies,
            "skills": self.skills,
            "technologies": self.technologies,
            "domains": self.domains,
        }


def ground_intent_to_corpus(
    query: str,
    intent: CandidateSearchIntent,
    vocabulary: SearchVocabulary,
) -> CandidateSearchIntent:
    """Canonicalize LLM output and discard unsupported hard constraints."""
    cities = _detect_in_query(query, vocabulary.cities, aliases=_CITY_ALIASES)
    countries = _detect_in_query(query, vocabulary.countries)
    companies = _detect_in_query(
        query,
        vocabulary.companies,
        aliases=_COMPANY_ALIASES,
    )

    explicit_skills = _detect_in_query(query, vocabulary.skills)
    explicit_technologies = _detect_in_query(query, vocabulary.technologies)
    explicit_domains = _detect_in_query(query, vocabulary.domains)
    required_skills = _intersection(intent.required_skills, explicit_skills)
    required_technologies = _intersection(
        intent.required_technologies,
        explicit_technologies,
    )
    required_domains = _intersection(intent.required_domains, explicit_domains)

    return intent.model_copy(
        update={
            "location": LocationIntent(
                country=countries[0] if countries else None,
                city=cities[0] if cities else None,
                cities=cities,
            ),
            "companies": companies,
            "required_skills": required_skills,
            "required_technologies": required_technologies,
            "required_domains": required_domains,
        }
    )


def _intersection(values: list[str], explicit: list[str]) -> list[str]:
    explicit_names = {normalize_name(value): value for value in explicit}
    return list(
        dict.fromkeys(
            explicit_names[normalize_name(value)]
            for value in values
            if normalize_name(value) in explicit_names
        )
    )


def _detect_in_query(
    query: str,
    choices: tuple[str, ...],
    *,
    aliases: dict[str, str] | None = None,
) -> list[str]:
    normalized_query = normalize_name(query)
    tokens = normalized_query.split()
    phrases = {
        " ".join(tokens[start : start + size])
        for size in range(1, min(3, len(tokens)) + 1)
        for start in range(len(tokens) - size + 1)
    }
    detected: list[str] = []
    for choice in choices:
        choice_name = normalize_name(choice)
        alias_names = [
            alias
            for alias, target in (aliases or {}).items()
            if target == choice_name
        ]
        if (
            choice_name in normalized_query
            or any(alias in phrases for alias in alias_names)
            or any(
                len(phrase) >= 4
                and _similarity(phrase, choice_name) >= 0.82
                for phrase in phrases
            )
        ):
            detected.append(choice)
    return detected


def _best_match(
    value: str,
    choices: tuple[str, ...],
    *,
    aliases: dict[str, str] | None = None,
) -> str | None:
    normalized = normalize_name(value)
    normalized = (aliases or {}).get(normalized, normalized)
    by_name = {normalize_name(choice): choice for choice in choices}
    if normalized in by_name:
        return by_name[normalized]
    scored = sorted(
        (
            _similarity(normalized, choice_name),
            choice,
        )
        for choice_name, choice in by_name.items()
    )
    if scored and scored[-1][0] >= 0.82:
        return scored[-1][1]
    return None


def _similarity(left: str, right: str) -> float:
    return max(
        SequenceMatcher(None, left_form, right_form).ratio()
        for left_form in _comparison_forms(left)
        for right_form in _comparison_forms(right)
    )


def _comparison_forms(value: str) -> set[str]:
    normalized = normalize_name(value)
    forms = {normalized}
    if _is_cyrillic_phrase(normalized):
        # Common Russian case endings: Казань/Казани, Яндекс/Яндекса,
        # Екатеринбург/Екатеринбурге. This is deliberately a comparison key,
        # never a replacement for the canonical value stored in the corpus.
        stem = normalized.rstrip("аеиоуыюяь")
        if len(stem) >= 3:
            forms.add(stem)
    return forms


def _is_cyrillic_phrase(value: str) -> bool:
    return bool(value) and all(
        ("а" <= character <= "я")  # noqa: RUF001
        or character in {"ё", " ", "-"}
        for character in value
    )
