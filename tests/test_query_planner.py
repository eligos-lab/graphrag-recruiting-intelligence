from app.retrieval.intent import CandidateSearchIntent, LocationIntent
from app.retrieval.planner import QueryPlanner, RetrievalOperation
from app.retrieval.query_understanding import enrich_free_form_intent


def test_query_planner_selects_safe_retrieval_operations() -> None:
    intent = CandidateSearchIntent(
        role="backend engineer",
        location=LocationIntent(country="Germany"),
        required_domains=["fintech"],
        semantic_query="distributed payment systems",
    )

    plan = QueryPlanner().plan(intent)

    assert plan.has_hard_filters is True
    assert plan.operations == [
        RetrievalOperation.STRUCTURED,
        RetrievalOperation.VECTOR,
        RetrievalOperation.GRAPH,
    ]


def test_query_planner_never_contains_executable_query_text() -> None:
    plan = QueryPlanner().plan(CandidateSearchIntent())

    assert plan.operations == [RetrievalOperation.STRUCTURED]
    assert set(plan.model_dump()) == {"operations", "has_hard_filters"}


def test_free_form_understanding_recognizes_moscow_case_form_as_a_hard_city() -> None:
    intent = enrich_free_form_intent(
        "Найди разработчиков в Москве, если нет — никого не присылай",
        CandidateSearchIntent(semantic_query="разработчики"),
    )

    assert intent.location.city == "Москва"
    assert QueryPlanner().plan(intent).has_hard_filters is True


def test_free_form_understanding_handles_mlops_and_candidate_age() -> None:
    intent = enrich_free_form_intent(
        "Ищу мл-инженера старше 18 лет",
        CandidateSearchIntent(min_years_experience=18, semantic_query="мл-инженер"),
    )

    assert intent.required_skills == ["MLOps"]
    assert intent.min_years_experience is None
