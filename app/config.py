from functools import lru_cache
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
    app_version: str = "0.3.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://graphrag:graphrag@localhost:5432/graphrag"
    )
    sql_echo: bool = False
    chunk_max_characters: int = Field(default=2_000, ge=500, le=20_000)
    embedding_api_key: SecretStr | None = None
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = Field(default=1_536, ge=1, le=16_000)
    embedding_batch_size: int = Field(default=128, ge=1, le=2_048)
    embedding_timeout_seconds: float = Field(default=60.0, gt=0, le=600)


@lru_cache
def get_settings() -> Settings:
    return Settings()
