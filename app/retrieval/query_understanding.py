"""Deterministic guardrails around LLM intent extraction for free-form recruiting queries."""

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
    "москва": "Москва",
    "москве": "Москва",
    "москвы": "Москва",
    "москву": "Москва",
    "moscow": "Moscow",
}


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
    city = next(
        (canonical for alias, canonical in _CITY_ALIASES.items() if alias in normalized),
        intent.location.city,
    )
    return intent.model_copy(
        update={
            "semantic_query": semantic_query,
            "preferred_technologies": preferred_technologies,
            "location": LocationIntent(country=intent.location.country, city=city),
        }
    )
