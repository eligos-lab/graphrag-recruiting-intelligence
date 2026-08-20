from pydantic import BaseModel

from app.inference.models import InferenceProposal
from app.reasoning.multihop import MultiHopResult
from app.retrieval.models import CandidateEvidence, CandidateProfile


class CandidateDetailResponse(BaseModel):
    candidate: CandidateProfile
    evidence: list[CandidateEvidence]


class CandidateGraphResponse(MultiHopResult):
    pass


class CandidateInferencesResponse(BaseModel):
    inferences: list[InferenceProposal]
