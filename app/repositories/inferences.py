from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inference.models import (
    InferenceProposal,
    InferenceStatus,
    InferenceType,
)
from app.infrastructure.database.models import CandidateInferenceModel


class InferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, proposals: list[InferenceProposal]) -> int:
        persisted = 0
        for proposal in proposals:
            model = await self.session.scalar(
                select(CandidateInferenceModel).where(
                    CandidateInferenceModel.person_id == proposal.person_id,
                    CandidateInferenceModel.inference_type == proposal.inference_type.value,
                    CandidateInferenceModel.claim == proposal.claim,
                )
            )
            if model is None:
                model = CandidateInferenceModel(
                    person_id=proposal.person_id,
                    inference_type=proposal.inference_type.value,
                    claim=proposal.claim,
                )
                self.session.add(model)
            model.confidence = proposal.confidence
            model.reason = proposal.reason
            model.evidence_ids = [str(value) for value in proposal.evidence_ids]
            model.status = proposal.status.value
            persisted += 1
        await self.session.commit()
        return persisted

    async def sync_for_person(
        self,
        person_id: UUID,
        proposals: list[InferenceProposal],
    ) -> int:
        existing = list(
            await self.session.scalars(
                select(CandidateInferenceModel).where(
                    CandidateInferenceModel.person_id == person_id
                )
            )
        )
        by_key = {(model.inference_type, model.claim): model for model in existing}
        expected = {(item.inference_type.value, item.claim) for item in proposals}
        for model in existing:
            key = (model.inference_type, model.claim)
            if model.status == InferenceStatus.UNVERIFIED.value and key not in expected:
                await self.session.delete(model)

        persisted = 0
        for proposal in proposals:
            key = (proposal.inference_type.value, proposal.claim)
            target = by_key.get(key)
            if target is not None and target.status != InferenceStatus.UNVERIFIED.value:
                continue
            if target is None:
                target = CandidateInferenceModel(
                    person_id=proposal.person_id,
                    inference_type=proposal.inference_type.value,
                    claim=proposal.claim,
                )
                self.session.add(target)
            target.confidence = proposal.confidence
            target.reason = proposal.reason
            target.evidence_ids = [str(value) for value in proposal.evidence_ids]
            target.status = proposal.status.value
            persisted += 1
        await self.session.commit()
        return persisted

    async def list_for_person(self, person_id: UUID) -> list[InferenceProposal]:
        models = list(
            await self.session.scalars(
                select(CandidateInferenceModel)
                .where(CandidateInferenceModel.person_id == person_id)
                .order_by(
                    CandidateInferenceModel.inference_type,
                    CandidateInferenceModel.claim,
                )
            )
        )
        return [
            InferenceProposal(
                person_id=model.person_id,
                inference_type=InferenceType(model.inference_type),
                claim=model.claim,
                confidence=model.confidence,
                reason=model.reason,
                evidence_ids=[UUID(value) for value in model.evidence_ids],
                status=InferenceStatus(model.status),
            )
            for model in models
        ]
