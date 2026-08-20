from collections.abc import Sequence

from app.inference.models import InferenceProposal, InferenceType
from app.ingestion.normalization import normalize_name
from app.retrieval.models import CandidateEvidence, CandidateProfile


class InferenceEngine:
    def infer_expertise(
        self,
        profile: CandidateProfile,
        evidence: Sequence[CandidateEvidence],
    ) -> list[InferenceProposal]:
        proposals: list[InferenceProposal] = []
        for domain in profile.domains:
            normalized_domain = normalize_name(domain)
            supporting = [
                item.chunk_id
                for item in evidence
                if item.chunk_id is not None and normalized_domain in normalize_name(item.content)
            ]
            supporting = list(dict.fromkeys(supporting))
            if len(supporting) < 2:
                continue
            confidence = min(0.55 + len(supporting) * 0.08, 0.87)
            proposals.append(
                InferenceProposal(
                    person_id=profile.person_id,
                    inference_type=InferenceType.EXPERTISE,
                    claim=f"Likely has sustained expertise in {domain}",
                    confidence=confidence,
                    reason=(
                        f"The domain appears in {len(supporting)} independent evidence chunks; "
                        "this is an inference, not a verified proficiency level."
                    ),
                    evidence_ids=supporting,
                )
            )
        return proposals

    def infer_similarity(
        self,
        profile: CandidateProfile,
        peer: CandidateProfile,
        evidence: Sequence[CandidateEvidence],
    ) -> InferenceProposal | None:
        own_terms = self._profile_terms(profile)
        peer_terms = self._profile_terms(peer)
        union = own_terms | peer_terms
        similarity = len(own_terms & peer_terms) / len(union) if union else 0
        evidence_ids = list(
            dict.fromkeys(item.chunk_id for item in evidence if item.chunk_id is not None)
        )
        if similarity < 0.5 or not evidence_ids:
            return None
        return InferenceProposal(
            person_id=profile.person_id,
            inference_type=InferenceType.SIMILARITY,
            claim=f"Likely has a similar professional background to {peer.full_name}",
            confidence=min(0.45 + similarity * 0.4, 0.85),
            reason=(
                f"Jaccard overlap across recorded skills, technologies, and domains is "
                f"{similarity:.2f}."
            ),
            evidence_ids=evidence_ids,
        )

    def infer_relationship(
        self,
        profile: CandidateProfile,
        peer: CandidateProfile,
        evidence: Sequence[CandidateEvidence],
    ) -> InferenceProposal | None:
        shared_companies = {normalize_name(value) for value in profile.companies} & {
            normalize_name(value) for value in peer.companies
        }
        evidence_ids = list(
            dict.fromkeys(item.chunk_id for item in evidence if item.chunk_id is not None)
        )
        if not shared_companies or not evidence_ids:
            return None
        companies = ", ".join(sorted(shared_companies))
        return InferenceProposal(
            person_id=profile.person_id,
            inference_type=InferenceType.RELATIONSHIP,
            claim=f"May have shared a professional context with {peer.full_name}",
            confidence=0.65,
            reason=(
                f"Both profiles reference the same company or organization ({companies}), but "
                "employment-date overlap is not verified."
            ),
            evidence_ids=evidence_ids,
        )

    @staticmethod
    def _profile_terms(profile: CandidateProfile) -> set[str]:
        return {
            normalize_name(value)
            for value in [*profile.skills, *profile.technologies, *profile.domains]
        }
