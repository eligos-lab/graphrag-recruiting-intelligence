"""Deterministic guardrails around LLM intent extraction for free-form recruiting queries."""

import re

from app.ingestion.normalization import normalize_name
from app.retrieval.intent import CandidateSearchIntent, LocationIntent

_SEMANTIC_EXPANSIONS = {
    "ai": ("machine learning", "ml", "llm", "mlops"),
    "ии": ("machine learning", "ml", "llm", "mlops"),
    "искусственный интеллект": ("machine learning", "ml", "llm", "mlops"),
    "machine learning": ("ml", "ml engineer", "mlops"),
    "ml": ("machine learning", "ml engineer", "mlops"),
}

# Local LLMs can occasionally miss Russian case forms while extracting a
# structured location.  These aliases make an explicit city constraint
# deterministic before retrieval begins.
_CITY_ALIASES = {
    "берлин": "Berlin",
    "берлина": "Berlin",
    "берлине": "Berlin",
    "варшава": "Warsaw",
    "варшаве": "Warsaw",
    "варшавы": "Warsaw",
    "лондон": "London",
    "лондоне": "London",
    "лондона": "London",
    "амстердам": "Amsterdam",
    "амстердаме": "Amsterdam",
    "амстердама": "Amsterdam",
    "лиссабон": "Lisbon",
    "лиссабоне": "Lisbon",
    "лиссабона": "Lisbon",
    "москва": "Москва",
    "москве": "Москва",
    "москвы": "Москва",
    "москву": "Москва",
    "санкт петербург": "Санкт-Петербург",
    "санкт петербурге": "Санкт-Петербург",
    "петербург": "Санкт-Петербург",
    "петербурге": "Санкт-Петербург",
    "казань": "Казань",
    "казани": "Казань",
    "екатеринбург": "Екатеринбург",
    "екатеринбурге": "Екатеринбург",
    "новосибирск": "Новосибирск",
    "новосибирске": "Новосибирск",
    "moscow": "Moscow",
}

_AGE_PATTERNS = ("старше ", "младше ", "возраст", "лет от роду")
_MLOPS_TERMS = ("млопс", "mlops", "мл инженер", "ml engineer", "machine learning engineer")
_PYTHON_TERMS = ("python", "питон")
_MIN_AGE = re.compile(r"(?:старше|от)\s+(\d{2})\s+лет")
_MAX_AGE = re.compile(r"(?:младше|до)\s+(\d{2})\s+лет")


def enrich_free_form_intent(query: str, intent: CandidateSearchIntent) -> CandidateSearchIntent:
    """Expand project context without turning an inference into a hard filter."""
    normalized = normalize_name(query)
    expansions = [
        value
        for trigger, values in _SEMANTIC_EXPANSIONS.items()
        if trigger in normalized
        for value in values
    ]
    semantic_query = " ".join(dict.fromkeys([intent.semantic_query or query, *expansions]))
    preferred_technologies = list(intent.preferred_technologies)
    if expansions:
        preferred_technologies = list(
            dict.fromkeys([*preferred_technologies, "Machine Learning", "MLOps"])
        )
    detected_cities = list(
        dict.fromkeys(
            canonical for alias, canonical in _CITY_ALIASES.items() if alias in normalized
        )
    )
    cities = list(
        dict.fromkeys([*intent.location.cities, *detected_cities])
    )
    city = intent.location.city or (cities[0] if cities else None)
    mentions_age = any(marker in normalized for marker in _AGE_PATTERNS)
    mentions_mlops = any(term in normalized for term in _MLOPS_TERMS)
    required_skills = list(intent.required_skills)
    required_technologies = list(intent.required_technologies)
    preferred_skills = list(intent.preferred_skills)
    companies = list(intent.companies)
    if mentions_mlops:
        # MLOps is stored as either a skill or a technology in real corpora;
        # retrieval handles both categories while ranking treats it as a fact.
        required_skills = list(dict.fromkeys([*required_skills, "MLOps"]))
        required_technologies = [
            item for item in required_technologies if normalize_name(item) != "mlops"
        ]
        preferred_skills = list(dict.fromkeys([*preferred_skills, "Machine Learning"]))
    if any(term in normalized for term in _PYTHON_TERMS):
        required_skills = list(dict.fromkeys([*required_skills, "Python"]))
    if "мтс" in normalized or "mts" in normalized:
        companies = list(dict.fromkeys([*companies, "МТС"]))  # noqa: RUF001
    min_age_match = _MIN_AGE.search(normalized)
    max_age_match = _MAX_AGE.search(normalized)
    return intent.model_copy(
        update={
            "semantic_query": semantic_query,
            "preferred_technologies": preferred_technologies,
            "preferred_skills": preferred_skills,
            "required_skills": required_skills,
            "required_technologies": required_technologies,
            "companies": companies,
            "location": LocationIntent(
                country=intent.location.country,
                city=city,
                cities=cities,
            ),
            "min_years_experience": None if mentions_age else intent.min_years_experience,
            "min_age": int(min_age_match.group(1)) if min_age_match else intent.min_age,
            "max_age": int(max_age_match.group(1)) if max_age_match else intent.max_age,
        }
    )
