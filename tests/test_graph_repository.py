from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from neo4j import AsyncDriver

from app.graph.models import GraphNodeSnapshot, PersonGraphSnapshot
from app.graph.neo4j import Neo4jGraphRepository
from app.retrieval.intent import CandidateSearchIntent


class FakeAsyncDriver:
    def __init__(self, person_id: UUID) -> None:
        self.person_id = person_id
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    async def execute_query(self, query: str, **parameters: Any) -> Any:
        self.calls.append((query, parameters))
        if "MATCH path=" in query:
            return (
                [
                    {
                        "person_id": str(self.person_id),
                        "nodes": ["Ada", "Fintech"],
                        "relationships": ["SPECIALIZES_IN"],
                        "evidence_ids": [str(uuid4())],
                    }
                ],
                None,
                None,
            )
        if "RETURN p.id AS person_id" in query:
            return ([{"person_id": str(self.person_id)}], None, None)
        return ([], None, None)

    async def close(self) -> None:
        self.closed = True


async def test_graph_repository_parameterizes_values_and_uses_fixed_relationships() -> None:
    person_id = uuid4()
    fake_driver = FakeAsyncDriver(person_id)
    repository = Neo4jGraphRepository(cast(AsyncDriver, fake_driver))
    malicious_name = 'Kafka"}) MATCH (secret) RETURN secret //'
    snapshot = PersonGraphSnapshot(
        id=person_id,
        full_name="Ada Lovelace",
        skills=[
            GraphNodeSnapshot(
                id=uuid4(),
                name=malicious_name,
                normalized_name="kafka",
                evidence_ids=[uuid4()],
            )
        ],
    )

    await repository.sync_person(snapshot)

    assert all(malicious_name not in query for query, _ in fake_driver.calls)
    assert any(
        call[1].get("items", [{}])[0].get("name") == malicious_name
        for call in fake_driver.calls
        if call[1].get("items")
    )
    assert any("HAS_SKILL" in query for query, _ in fake_driver.calls)


async def test_graph_search_and_bounded_paths_are_mapped_to_domain_contracts() -> None:
    person_id = uuid4()
    fake_driver = FakeAsyncDriver(person_id)
    repository = Neo4jGraphRepository(cast(AsyncDriver, fake_driver))

    ids = await repository.search_ids(
        CandidateSearchIntent(required_domains=["FinTech"]),
        limit=20,
    )
    paths = await repository.paths({person_id}, max_hops=2, limit=10)

    assert ids == {person_id}
    assert paths[0].relationships == ["SPECIALIZES_IN"]
    search_parameters = next(
        parameters for query, parameters in fake_driver.calls if "RETURN p.id AS person_id" in query
    )
    assert search_parameters["domains"] == ["fintech"]
    assert any("*1..2" in query for query, _ in fake_driver.calls)


async def test_graph_paths_reject_unbounded_depth() -> None:
    repository = Neo4jGraphRepository(cast(AsyncDriver, FakeAsyncDriver(uuid4())))

    with pytest.raises(ValueError, match="max_hops"):
        await repository.paths({uuid4()}, max_hops=4, limit=10)
