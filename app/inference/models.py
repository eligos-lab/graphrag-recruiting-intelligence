from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InferenceType(StrEnum):
    EXPERTISE = "expertise"
    RELATIONSHIP = "relationship"
    SIMILARITY = "similarity"


class InferenceStatus(StrEnum):
    UNVERIFIED = "unverified"
    REVIEWED = "reviewed"
    REJECTED = "rejected"


class InferenceProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_id: UUID
    inference_type: InferenceType
    claim: str
    confidence: float = Field(gt=0, lt=1)
    reason: str
    evidence_ids: list[UUID] = Field(min_length=1)
    status: InferenceStatus = InferenceStatus.UNVERIFIED
