from app.retrieval.intent import CandidateSearchIntent, LocationIntent
from app.retrieval.planner import QueryPlanner, RetrievalOperation


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
