from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.api.dependencies import GraphRepositoryDependency, SessionDependency
from app.inference.engine import InferenceEngine
from app.reasoning.multihop import MultiHopReasoner
from app.repositories.inferences import InferenceRepository
from app.repositories.search import SqlAlchemyStructuredSearchRepository
from app.schemas.candidates import (
    CandidateDetailResponse,
    CandidateGraphResponse,
    CandidateInferencesResponse,
)
from app.services.inferences import InferenceService
from app.services.resume_export import render_docx, render_pdf

router = APIRouter()


def _attachment_header(filename: str) -> str:
    safe_fallback = "resume"
    return f"attachment; filename={safe_fallback}; filename*=UTF-8''{quote(filename)}"


@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
async def candidate_detail(
    candidate_id: UUID,
    session: SessionDependency,
) -> CandidateDetailResponse:
    repository = SqlAlchemyStructuredSearchRepository(session)
    profiles = await repository.profiles({candidate_id})
    profile = profiles.get(candidate_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    evidence = await repository.evidence({candidate_id})
    return CandidateDetailResponse(
        candidate=profile,
        evidence=evidence.get(candidate_id, []),
    )


@router.get("/{candidate_id}/resume.{file_format}")
async def download_resume(
    candidate_id: UUID,
    file_format: str,
    session: SessionDependency,
) -> Response:
    profile = (await SqlAlchemyStructuredSearchRepository(session).profiles({candidate_id})).get(
        candidate_id
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    filename = f"{profile.full_name.replace(' ', '_')}_resume"
    if file_format == "pdf":
        return Response(
            render_pdf(profile),
            media_type="application/pdf",
            headers={"Content-Disposition": _attachment_header(f"{filename}.pdf")},
        )
    if file_format == "docx":
        return Response(
            render_docx(profile),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": _attachment_header(f"{filename}.docx")},
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use pdf or docx")


@router.get("/{candidate_id}/graph", response_model=CandidateGraphResponse)
async def candidate_graph(
    candidate_id: UUID,
    graph_repository: GraphRepositoryDependency,
    max_hops: int = Query(default=3, ge=1, le=3),
) -> CandidateGraphResponse:
    result = await MultiHopReasoner(graph_repository).explain(
        candidate_id,
        max_hops=max_hops,
    )
    return CandidateGraphResponse.model_validate(result.model_dump())


@router.get("/{candidate_id}/inferences", response_model=CandidateInferencesResponse)
async def candidate_inferences(
    candidate_id: UUID,
    session: SessionDependency,
) -> CandidateInferencesResponse:
    inferences = await InferenceRepository(session).list_for_person(candidate_id)
    return CandidateInferencesResponse(inferences=inferences)


@router.post("/{candidate_id}/inferences/rebuild", response_model=CandidateInferencesResponse)
async def rebuild_candidate_inferences(
    candidate_id: UUID,
    session: SessionDependency,
) -> CandidateInferencesResponse:
    structured_repository = SqlAlchemyStructuredSearchRepository(session)
    profile = await structured_repository.profiles({candidate_id})
    if candidate_id not in profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    service = InferenceService(
        structured_repository,
        InferenceRepository(session),
        InferenceEngine(),
    )
    inferences = await service.rebuild_person(candidate_id)
    return CandidateInferencesResponse(inferences=inferences)
