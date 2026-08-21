from app.retrieval.intent import CandidateSearchIntent, LocationIntent
from app.retrieval.metadata_grounding import SearchVocabulary, ground_intent_to_corpus

VOCABULARY = SearchVocabulary(
    cities=("Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск"),
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


def test_russian_city_inflections_and_typos_are_grounded_generically() -> None:
    examples = {
        "разработчик из Казани": "Казань",
        "инженер в Екатеринбурге": "Екатеринбург",
        "кандидат из Новасибирска": "Новосибирск",
    }
    for query, city in examples.items():
        result = ground_intent_to_corpus(
            query,
            CandidateSearchIntent(location=LocationIntent(city=query.split()[-1])),
            VOCABULARY,
        )
        assert result.location.city == city


def test_any_known_company_cannot_survive_as_a_location() -> None:
    result = ground_intent_to_corpus(
        "разработчик из яндекса",
        CandidateSearchIntent(
            location=LocationIntent(city="Яндекса"),
            companies=["Яндекса"],
        ),
        VOCABULARY,
    )

    assert result.location.city is None
    assert result.companies == ["Яндекс"]


def test_unknown_explicit_company_and_city_remain_blocking_constraints() -> None:
    microsoft = ground_intent_to_corpus(
        "разработчик, работавший в компании Microsoft",
        CandidateSearchIntent(companies=["Microsoft"]),
        VOCABULARY,
    )
    unknown_city = ground_intent_to_corpus(
        "сотрудник из несуществующего города",
        CandidateSearchIntent(location=LocationIntent(city="несуществующий город")),
        VOCABULARY,
    )

    assert microsoft.unresolved_constraints == ["company:Microsoft"]
    assert unknown_city.unresolved_constraints == ["city:несуществующий город"]


def test_valid_but_unmentioned_llm_location_is_discarded() -> None:
    result = ground_intent_to_corpus(
        "разработчик, работавший в компании Microsoft",
        CandidateSearchIntent(
            location=LocationIntent(city="Москва"),
            companies=["Microsoft"],
        ),
        VOCABULARY,
    )

    assert result.location.city is None
    assert result.unresolved_constraints == ["company:Microsoft"]
