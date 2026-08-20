from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GRAPHRAG_",
        extra="ignore",
    )

    app_name: str = "GraphRAG Recruiting Intelligence"
    app_version: str = "1.0.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://graphrag:graphrag@localhost:5432/graphrag"
    )
    sql_echo: bool = False
    chunk_max_characters: int = Field(default=2_000, ge=500, le=20_000)
    embedding_provider: Literal["openai", "ollama"] = "openai"
    embedding_api_key: SecretStr | None = None
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = Field(default=1_536, ge=1, le=16_000)
    embedding_batch_size: int = Field(default=128, ge=1, le=2_048)
    embedding_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    llm_provider: Literal["openai", "ollama"] = "openai"
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = Field(default=90.0, gt=0, le=600)
    llm_max_input_characters: int = Field(default=200_000, ge=1_000, le=2_000_000)
    neo4j_uri: str = "neo4j://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("graphrag-password")
    neo4j_database: str = "neo4j"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    ingestion_data_root: Path = Path("data")
    upload_max_file_size_mb: int = Field(default=25, ge=1, le=200)
    api_access_key: SecretStr | None = None
    api_rate_limit_per_minute: int = Field(default=120, ge=10, le=10_000)
    pdf_max_file_size_mb: int = Field(default=25, ge=1, le=200)
    search_candidate_pool_size: int = Field(default=100, ge=1, le=1_000)
    vector_search_limit: int = Field(default=100, ge=1, le=1_000)
    graph_search_limit: int = Field(default=100, ge=1, le=1_000)
    max_graph_hops: int = Field(default=3, ge=1, le=3)
    ranking_semantic_weight: float = Field(default=0.30, ge=0, le=1)
    ranking_skill_weight: float = Field(default=0.25, ge=0, le=1)
    ranking_domain_weight: float = Field(default=0.15, ge=0, le=1)
    ranking_experience_weight: float = Field(default=0.10, ge=0, le=1)
    ranking_graph_weight: float = Field(default=0.10, ge=0, le=1)
    ranking_location_weight: float = Field(default=0.05, ge=0, le=1)
    ranking_preference_weight: float = Field(default=0.05, ge=0, le=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
