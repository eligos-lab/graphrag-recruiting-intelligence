from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GRAPHRAG_",
        extra="ignore",
    )

    app_name: str = "GraphRAG Recruiting Intelligence"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = Field(
        default="postgresql+asyncpg://graphrag:graphrag@localhost:5432/graphrag"
    )
    sql_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
