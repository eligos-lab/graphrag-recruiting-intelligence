from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthChecks(BaseModel):
    model_config = ConfigDict(frozen=True)

    database: bool


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["healthy", "degraded"]
    service: str
    version: str
    checks: HealthChecks
