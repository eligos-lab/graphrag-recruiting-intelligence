from uuid import UUID

from app.inference.engine import InferenceEngine
from app.inference.models import InferenceProposal
from app.repositories.inferences import InferenceRepository
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.protocols import StructuredSearchRepository


class InferenceService:
    def __init__(
        self,
        structured_repository: StructuredSearchRepository,
        inference_repository: InferenceRepository,
        engine: InferenceEngine | None = None,
    ) -> None:
        self.structured_repository = structured_repository
        self.inference_repository = inference_repository
        self.engine = engine or InferenceEngine()

    async def rebuild_person(self, person_id: UUID) -> list[InferenceProposal]:
        all_ids = await self.structured_repository.filter_ids(
            CandidateSearchIntent(),
            limit=1_000,
        )
        profiles = await self.structured_repository.profiles(all_ids | {person_id})
        profile = profiles.get(person_id)
        if profile is None:
            return []
        evidence = await self.structured_repository.evidence(set(profiles))
        own_evidence = evidence.get(person_id, [])
        proposals = self.engine.infer_expertise(profile, own_evidence)
        for peer_id, peer in profiles.items():
            if peer_id == person_id:
                continue
            combined_evidence = [*own_evidence, *evidence.get(peer_id, [])]
            similarity = self.engine.infer_similarity(profile, peer, combined_evidence)
            relationship = self.engine.infer_relationship(profile, peer, combined_evidence)
            if similarity is not None:
                proposals.append(similarity)
            if relationship is not None:
                proposals.append(relationship)
        await self.inference_repository.sync_for_person(person_id, proposals)
        return proposals
