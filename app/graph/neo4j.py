from collections.abc import Sequence
from typing import Any
from uuid import UUID

from neo4j import AsyncDriver, AsyncGraphDatabase, RoutingControl

from app.graph.models import GraphNodeSnapshot, PersonGraphSnapshot
from app.ingestion.normalization import normalize_name
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import GraphPath

_CONSTRAINTS = (
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (n:Skill) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT technology_id IF NOT EXISTS FOR (n:Technology) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (n:Project) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT university_id IF NOT EXISTS FOR (n:University) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT domain_id IF NOT EXISTS FOR (n:Domain) REQUIRE n.id IS UNIQUE",
)

_SEARCH_QUERY = """
MATCH (p:Person)
WHERE (size($companies) = 0 OR ALL(value IN $companies WHERE EXISTS {
  MATCH (p)-[:WORKED_AT]->(company:Company {normalized_name: value})
}))
AND (size($projects) = 0 OR ALL(value IN $projects WHERE EXISTS {
  MATCH (p)-[:WORKED_ON]->(project:Project {normalized_name: value})
}))
AND (size($domains) = 0 OR ALL(value IN $domains WHERE
  EXISTS { MATCH (p)-[:SPECIALIZES_IN]->(:Domain {normalized_name: value}) }
  OR EXISTS {
    MATCH (p)-[:WORKED_AT]->(:Company)-[:OPERATES_IN]->(:Domain {normalized_name: value})
  }
  OR EXISTS {
    MATCH (p)-[:WORKED_ON]->(:Project)-[:BELONGS_TO]->(:Domain {normalized_name: value})
  }
))
RETURN p.id AS person_id
ORDER BY person_id
LIMIT $limit
"""

_ALLOWED_PATH_RELATIONSHIPS = (
    "WORKED_AT|HAS_SKILL|USED_TECHNOLOGY|WORKED_ON|STUDIED_AT|SPECIALIZES_IN|"
    "OPERATES_IN|USES|BELONGS_TO|WORKED_WITH|CONTRIBUTED_TO|SIMILAR_TO"
)


class Neo4jGraphRepository:
    def __init__(self, driver: AsyncDriver, *, database: str = "neo4j") -> None:
        self.driver = driver
        self.database = database

    @classmethod
    def connect(
        cls,
        *,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> "Neo4jGraphRepository":
        return cls(
            AsyncGraphDatabase.driver(uri, auth=(user, password)),
            database=database,
        )

    async def ensure_schema(self) -> None:
        for query in _CONSTRAINTS:
            await self.driver.execute_query(query, database_=self.database)

    async def sync_person(self, snapshot: PersonGraphSnapshot) -> None:
        await self.driver.execute_query(
            """
            MERGE (p:Person {id: $id})
            SET p.full_name = $full_name,
                p.country = $country,
                p.current_title = $current_title,
                p.evidence_ids = $evidence_ids
            """,
            id=str(snapshot.id),
            full_name=snapshot.full_name,
            country=snapshot.country,
            current_title=snapshot.current_title,
            evidence_ids=[str(value) for value in snapshot.evidence_ids],
            database_=self.database,
        )
        await self._replace_person_relations(
            snapshot.id, "Company", "WORKED_AT", snapshot.companies
        )
        await self._replace_person_relations(snapshot.id, "Skill", "HAS_SKILL", snapshot.skills)
        await self._replace_person_relations(
            snapshot.id,
            "Technology",
            "USED_TECHNOLOGY",
            snapshot.technologies,
        )
        await self._replace_person_relations(snapshot.id, "Project", "WORKED_ON", snapshot.projects)
        await self._replace_person_relations(
            snapshot.id,
            "University",
            "STUDIED_AT",
            snapshot.universities,
        )
        await self._replace_person_relations(
            snapshot.id,
            "Domain",
            "SPECIALIZES_IN",
            snapshot.domains,
        )
        for company in snapshot.companies:
            await self._replace_entity_relations(
                "Company", company.id, "Domain", "OPERATES_IN", company.domains
            )
        for project in snapshot.projects:
            await self._replace_entity_relations(
                "Project", project.id, "Technology", "USES", project.technologies
            )
            await self._replace_entity_relations(
                "Project", project.id, "Domain", "BELONGS_TO", project.domains
            )

    async def _replace_person_relations(
        self,
        person_id: UUID,
        target_label: str,
        relationship: str,
        items: Sequence[GraphNodeSnapshot],
    ) -> None:
        await self._replace_entity_relations(
            "Person",
            person_id,
            target_label,
            relationship,
            items,
        )

    async def _replace_entity_relations(
        self,
        source_label: str,
        source_id: UUID,
        target_label: str,
        relationship: str,
        items: Sequence[GraphNodeSnapshot],
    ) -> None:
        allowed = {
            ("Person", "Company", "WORKED_AT"),
            ("Person", "Skill", "HAS_SKILL"),
            ("Person", "Technology", "USED_TECHNOLOGY"),
            ("Person", "Project", "WORKED_ON"),
            ("Person", "University", "STUDIED_AT"),
            ("Person", "Domain", "SPECIALIZES_IN"),
            ("Company", "Domain", "OPERATES_IN"),
            ("Project", "Technology", "USES"),
            ("Project", "Domain", "BELONGS_TO"),
        }
        if (source_label, target_label, relationship) not in allowed:
            raise ValueError("Unsupported graph relationship")
        query = f"""
        MATCH (source:{source_label} {{id: $source_id}})
        OPTIONAL MATCH (source)-[old:{relationship}]->()
        DELETE old
        WITH DISTINCT source
        UNWIND $items AS item
        MERGE (target:{target_label} {{id: item.id}})
        SET target.name = item.name, target.normalized_name = item.normalized_name
        MERGE (source)-[relation:{relationship}]->(target)
        SET relation.evidence_ids = item.evidence_ids
        """
        await self.driver.execute_query(
            query,
            source_id=str(source_id),
            items=[self._node_parameters(item) for item in items],
            database_=self.database,
        )

    async def search_ids(self, intent: CandidateSearchIntent, *, limit: int) -> set[UUID]:
        records, _, _ = await self.driver.execute_query(
            _SEARCH_QUERY,
            companies=[normalize_name(value) for value in intent.companies],
            projects=[normalize_name(value) for value in intent.projects],
            domains=[normalize_name(value) for value in intent.required_domains],
            limit=limit,
            routing_=RoutingControl.READ,
            database_=self.database,
        )
        return {UUID(record["person_id"]) for record in records}

    async def paths(
        self,
        person_ids: set[UUID],
        *,
        max_hops: int,
        limit: int,
    ) -> list[GraphPath]:
        if not 1 <= max_hops <= 3:
            raise ValueError("max_hops must be between 1 and 3")
        if not person_ids:
            return []
        query = f"""
        MATCH path=(p:Person)-[:{_ALLOWED_PATH_RELATIONSHIPS}*1..{max_hops}]-(related)
        WHERE p.id IN $person_ids
        RETURN p.id AS person_id,
               [node IN nodes(path) | coalesce(node.full_name, node.name, node.id)] AS nodes,
               [relation IN relationships(path) | type(relation)] AS relationships,
               reduce(ids = [], relation IN relationships(path) |
                 ids + coalesce(relation.evidence_ids, [])) AS evidence_ids
        LIMIT $limit
        """
        records, _, _ = await self.driver.execute_query(
            query,
            person_ids=[str(value) for value in person_ids],
            limit=limit,
            routing_=RoutingControl.READ,
            database_=self.database,
        )
        return [
            GraphPath(
                person_id=UUID(record["person_id"]),
                nodes=list(record["nodes"]),
                relationships=list(record["relationships"]),
                evidence_ids=list(dict.fromkeys(UUID(value) for value in record["evidence_ids"])),
                score=1 / max(len(record["relationships"]), 1),
            )
            for record in records
        ]

    async def close(self) -> None:
        await self.driver.close()

    async def verify_connectivity(self) -> None:
        await self.driver.verify_connectivity(database=self.database)

    @staticmethod
    def _node_parameters(node: GraphNodeSnapshot) -> dict[str, Any]:
        return {
            "id": str(node.id),
            "name": node.name,
            "normalized_name": node.normalized_name,
            "evidence_ids": [str(value) for value in node.evidence_ids],
        }
