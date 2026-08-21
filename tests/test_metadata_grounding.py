from app.retrieval.intent import CandidateSearchIntent, LocationIntent
from app.retrieval.metadata_grounding import SearchVocabulary, ground_intent_to_corpus

VOCABULARY = SearchVocabulary(
    cities=("Москва", "Санкт-Петербург"),
    countries=("Россия",),
    companies=("МТС", "Яндекс"),  # noqa: RUF001
    skills=("Python", "SQL"),
)


def test_company_is_not_kept_as_a_hallucinated_city_or_skill() -> None:
    result = ground_intent_to_corpus(
        "разработчик из мтс",
        CandidateSearchIntent(
            role="разработчик",
            location=LocationIntent(city="мтс"),
            companies=["МТС"],  # noqa: RUF001
            required_skills=["Python"],
        ),
        VOCABULARY,
    )

    assert result.location.city is None
    assert result.location.cities == []
    assert result.companies == ["МТС"]  # noqa: RUF001
    assert result.required_skills == []


def test_city_aliases_typos_and_case_are_grounded_to_corpus_metadata() -> None:
    for query in ("МОСКВА", "мск", "масква", "московия"):  # noqa: RUF001
        result = ground_intent_to_corpus(
            query,
            CandidateSearchIntent(location=LocationIntent(city=query)),
            VOCABULARY,
        )
        assert result.location.city == "Москва"
