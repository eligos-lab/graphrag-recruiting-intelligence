from app.config import Settings
from app.llm.credentials import first_secret_value
from app.llm.providers.ollama import OllamaEmbeddingProvider, OllamaLanguageModelProvider
from app.llm.providers.openai import OpenAIEmbeddingProvider
from app.llm.providers.openai_responses import OpenAIResponsesProvider

type EmbeddingProviderClient = OpenAIEmbeddingProvider | OllamaEmbeddingProvider
type LanguageModelProviderClient = OpenAIResponsesProvider | OllamaLanguageModelProvider


class ProviderConfigurationError(RuntimeError):
    pass


def create_embedding_provider(settings: Settings) -> EmbeddingProviderClient:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            base_url=settings.embedding_base_url,
            timeout_seconds=settings.embedding_timeout_seconds,
        )
    api_key = first_secret_value(settings.embedding_api_key, settings.llm_api_key)
    if not api_key:
        raise ProviderConfigurationError("OpenAI embedding API key is not configured")
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
        base_url=settings.embedding_base_url,
        timeout_seconds=settings.embedding_timeout_seconds,
    )


def create_language_model_provider(settings: Settings) -> LanguageModelProviderClient:
    if settings.llm_provider == "ollama":
        return OllamaLanguageModelProvider(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    api_key = first_secret_value(settings.llm_api_key, settings.embedding_api_key)
    if not api_key:
        raise ProviderConfigurationError("OpenAI LLM API key is not configured")
    return OpenAIResponsesProvider(
        api_key=api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
    )
