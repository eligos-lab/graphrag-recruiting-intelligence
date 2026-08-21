import json
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.llm.protocols import LanguageModelProvider

if TYPE_CHECKING:
    from app.retrieval.metadata_grounding import SearchVocabulary


class LocationIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str | None = None
    city: str | None = None
    cities: list[str] = Field(default_factory=list)


class CandidateSearchIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_entity: Literal["person"] = "person"
    role: str | None = None
    seniority: str | None = None
    location: LocationIntent = Field(default_factory=LocationIntent)
    min_years_experience: float | None = Field(default=None, ge=0)
    min_age: int | None = Field(default=None, ge=14, le=100)
    max_age: int | None = Field(default=None, ge=14, le=100)
    required_skills: list[str] = Field(default_factory=list)
    required_technologies: list[str] = Field(default_factory=list)
    required_domains: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    preferred_technologies: list[str] = Field(default_factory=list)
    preferred_domains: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    unresolved_constraints: list[str] = Field(default_factory=list)
    semantic_query: str | None = None


class IntentParser:
    _INSTRUCTIONS = """Convert recruiting searches into the supplied schema.
Use only constraints explicitly stated by the user. Put mandatory requirements in required
fields and wishes in preferred fields. Preserve semantic experience concepts in semantic_query.
Treat an explicitly stated city or country as mandatory: never relax a location constraint or
replace it with candidates from another location, including when the request says "if none,
return nobody".
When several cities are acceptable, put them in location.cities; they are alternatives (OR),
not one combined city name.
Age is not work experience. Put explicit age requirements into min_age or max_age, and only
populate min_years_experience when the request explicitly mentions professional experience.
Classify every requested term into exactly one category; never duplicate a value across skills,
technologies, and domains. Programming languages and professional competencies are skills.
Named frameworks, infrastructure platforms, cloud services, databases, and developer tools are
technologies. Industry or business areas are domains. Kafka is a technology; Python is a skill;
Kubernetes and AWS are technologies; fintech is a domain.
Interpret semantic seniority naturally: "young", "junior", "entry-level" and "начинающий"
mean junior-level candidates with roughly 0-3 years of experience; preserve the project context
(for example AI/ML) in semantic_query even if it is not an explicit hard requirement.
Never produce SQL, Cypher, candidate facts, or candidate names not present in the request."""

    def __init__(
        self,
        provider: LanguageModelProvider,
        vocabulary: "SearchVocabulary | None" = None,
    ) -> None:
        self.provider = provider
        self.vocabulary = vocabulary

    async def parse(self, query: str) -> CandidateSearchIntent:
        instructions = self._INSTRUCTIONS
        if self.vocabulary is not None:
            instructions += (
                "\nResolve spelling variants, abbreviations and typos to these canonical corpus "
                "values. Never put a company into a location field or infer an unstated hard "
                "skill:\n"
                + json.dumps(self.vocabulary.as_prompt_data(), ensure_ascii=False)
            )
        intent = await self.provider.structured_output(
            instructions=instructions,
            prompt=query,
            response_model=CandidateSearchIntent,
        )
        if intent.semantic_query is None:
            intent = intent.model_copy(update={"semantic_query": query})
        if self.vocabulary is not None:
            from app.retrieval.metadata_grounding import ground_intent_to_corpus

            intent = ground_intent_to_corpus(query, intent, self.vocabulary)
        from app.retrieval.query_understanding import enrich_free_form_intent

        return enrich_free_form_intent(query, intent)
