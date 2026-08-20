from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ingestion.normalization import EntityNameNormalizer, normalize_name
from app.retrieval.intent import CandidateSearchIntent
from app.retrieval.models import (
    CandidateEvidence,
    CandidateMatch,
    CandidateProfile,
    CandidateReason,
    ClaimKind,
    GraphPath,
    ScoreBreakdown,
)


class RankingWeights(BaseModel):
    model_config = ConfigDict(frozen=True)

    semantic: float = Field(default=0.30, ge=0, le=1)
    skills: float = Field(default=0.25, ge=0, le=1)
    domains: float = Field(default=0.15, ge=0, le=1)
    experience: float = Field(default=0.10, ge=0, le=1)
    graph: float = Field(default=0.10, ge=0, le=1)
    location: float = Field(default=0.05, ge=0, le=1)
    preference: float = Field(default=0.05, ge=0, le=1)

    @model_validator(mode="after")
    def validate_total(self) -> "RankingWeights":
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("At least one ranking weight must be positive")
        return self


class CompositeRanker:
    def __init__(
        self,
        weights: RankingWeights | None = None,
        normalizer: EntityNameNormalizer | None = None,
    ) -> None:
        self.weights = weights or RankingWeights()
        self.normalizer = normalizer or EntityNameNormalizer()

    def rank(
        self,
        intent: CandidateSearchIntent,
        profiles: dict[UUID, CandidateProfile],
        evidence: dict[UUID, list[CandidateEvidence]],
        graph_paths: Sequence[GraphPath],
        *,
        limit: int,
    ) -> list[CandidateMatch]:
        paths_by_person: dict[UUID, list[GraphPath]] = {}
        for path in graph_paths:
            paths_by_person.setdefault(path.person_id, []).append(path)

        matches = [
            self._match(
                intent,
                profile,
                evidence.get(person_id, []),
                paths_by_person.get(person_id, []),
            )
            for person_id, profile in profiles.items()
        ]
        matches.sort(
            key=lambda item: (-item.score, item.full_name.casefold(), str(item.candidate_id))
        )
        return matches[:limit]

    def _match(
        self,
        intent: CandidateSearchIntent,
        profile: CandidateProfile,
        evidence: list[CandidateEvidence],
        paths: list[GraphPath],
    ) -> CandidateMatch:
        semantic = max(
            (item.score for item in evidence if item.source.value == "vector"),
            default=0.0,
        )
        required_skills = [*intent.required_skills, *intent.required_technologies]
        profile_skills = [*profile.skills, *profile.technologies]
        skill_score = self._match_ratio(required_skills, profile_skills, canonical=True)
        domain_score = self._match_ratio(intent.required_domains, profile.domains)
        experience_score = self._experience_score(intent, profile)
        graph_score = max((path.score for path in paths), default=0.0)
        location_score = self._location_score(intent, profile)
        preferred = [
            *intent.preferred_skills,
            *intent.preferred_technologies,
            *intent.preferred_domains,
        ]
        profile_preferences = [*profile.skills, *profile.technologies, *profile.domains]
        preference_score = self._match_ratio(preferred, profile_preferences, canonical=True)
        breakdown = ScoreBreakdown(
            semantic=semantic,
            skills=skill_score,
            domains=domain_score,
            experience=experience_score,
            graph=graph_score,
            location=location_score,
            preference=preference_score,
        )
        weighted = sum(
            getattr(breakdown, field) * weight
            for field, weight in self.weights.model_dump().items()
        )
        total_weight = sum(self.weights.model_dump().values())
        reasons = self._reasons(intent, evidence, paths)
        return CandidateMatch(
            candidate_id=profile.person_id,
            full_name=profile.full_name,
            score=max(0.0, min(1.0, weighted / total_weight)),
            breakdown=breakdown,
            evidence=evidence,
            reasons=reasons,
        )

    def _match_ratio(
        self,
        requested: Sequence[str],
        actual: Sequence[str],
        *,
        canonical: bool = False,
    ) -> float:
        if not requested:
            return 0.0
        normalize = self._canonical if canonical else normalize_name
        actual_names = {normalize(value) for value in actual}
        matches = sum(normalize(value) in actual_names for value in requested)
        return matches / len(requested)

    def _canonical(self, value: str) -> str:
        return self.normalizer.canonicalize(value).normalized_name

    @staticmethod
    def _experience_score(
        intent: CandidateSearchIntent,
        profile: CandidateProfile,
    ) -> float:
        scores: list[float] = []
        title = (profile.current_title or "").casefold()
        if intent.role:
            role_tokens = [token for token in intent.role.casefold().split() if len(token) > 2]
            scores.append(sum(token in title for token in role_tokens) / max(len(role_tokens), 1))
        if intent.seniority:
            scores.append(float(intent.seniority.casefold() in title))
        if intent.min_years_experience is not None:
            years = profile.years_experience or 0
            minimum = intent.min_years_experience
            scores.append(1.0 if minimum == 0 else min(years / minimum, 1.0))
        return sum(scores) / len(scores) if scores else 0.0

    @staticmethod
    def _location_score(
        intent: CandidateSearchIntent,
        profile: CandidateProfile,
    ) -> float:
        requested: list[bool] = []
        if intent.location.country:
            requested.append(
                (profile.country or "").casefold() == intent.location.country.casefold()
            )
        if intent.location.city:
            requested.append(intent.location.city.casefold() in (profile.location or "").casefold())
        return sum(requested) / len(requested) if requested else 0.0

    @staticmethod
    def _reasons(
        intent: CandidateSearchIntent,
        evidence: list[CandidateEvidence],
        paths: list[GraphPath],
    ) -> list[CandidateReason]:
        reasons: list[CandidateReason] = []
        for requirement in [*intent.required_skills, *intent.required_technologies]:
            supporting = CompositeRanker._supporting_ids(evidence, requirement)
            if not supporting:
                continue
            reasons.append(
                CandidateReason(
                    claim=f"Evidence mentions required skill or technology: {requirement}",
                    kind=ClaimKind.FACT,
                    evidence_ids=supporting,
                )
            )
        for requirement in intent.required_domains:
            supporting = CompositeRanker._supporting_ids(evidence, requirement)
            if not supporting:
                continue
            reasons.append(
                CandidateReason(
                    claim=f"Evidence mentions required domain: {requirement}",
                    kind=ClaimKind.FACT,
                    evidence_ids=supporting,
                )
            )
        for path in paths[:2]:
            if path.evidence_ids:
                reasons.append(
                    CandidateReason(
                        claim=" → ".join(path.nodes),
                        kind=ClaimKind.FACT,
                        evidence_ids=path.evidence_ids,
                    )
                )
        return reasons

    @staticmethod
    def _supporting_ids(
        evidence: Sequence[CandidateEvidence],
        requirement: str,
    ) -> list[UUID]:
        normalized = normalize_name(requirement)
        return list(
            dict.fromkeys(
                item.chunk_id
                for item in evidence
                if item.chunk_id is not None and normalized in normalize_name(item.content)
            )
        )
