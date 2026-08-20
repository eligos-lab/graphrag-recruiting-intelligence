from app.ingestion.schemas import CanonicalResume, ExtractedResume, SourceDocument
from app.llm.protocols import LanguageModelProvider


class LLMResumeParser:
    _INSTRUCTIONS = """Extract resume facts into the supplied schema.
Use only explicit text from the resume. Do not infer seniority, skills, dates, employers, domains,
or education. Use null or empty lists when data is absent."""

    def __init__(
        self,
        provider: LanguageModelProvider,
        *,
        max_input_characters: int = 200_000,
    ) -> None:
        self.provider = provider
        self.max_input_characters = max_input_characters

    async def parse(self, document: SourceDocument) -> CanonicalResume:
        if len(document.raw_text) > self.max_input_characters:
            raise ValueError(
                f"Resume text exceeds LLM input limit ({len(document.raw_text)} > "
                f"{self.max_input_characters})"
            )
        extracted = await self.provider.structured_output(
            instructions=self._INSTRUCTIONS,
            prompt=document.raw_text,
            response_model=ExtractedResume,
        )
        if extracted.full_name is None or not extracted.full_name.strip():
            raise ValueError(f"Resume {document.external_id} has no full name")
        return CanonicalResume(
            source=document.source,
            external_id=document.external_id,
            **extracted.model_dump(),
        )
