from app.config import get_settings
from app.graph.neo4j import Neo4jGraphRepository

settings = get_settings()
graph_repository = Neo4jGraphRepository.connect(
    uri=settings.neo4j_uri,
    user=settings.neo4j_user,
    password=settings.neo4j_password.get_secret_value(),
    database=settings.neo4j_database,
)
