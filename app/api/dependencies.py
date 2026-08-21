from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.generation.evidence import EvidenceAnswerGenerator
from app.infrastructure.cache import redis_client
from app.infrastructure.database.models import (
    CompanyModel,
    DomainModel,
    PersonModel,
    SkillModel,
    TechnologyModel,
)
from app.infrastructure.database.session import get_database_session
from app.infrastructure.graph import graph_repository
from app.llm.factory import (
    ProviderConfigurationError,
    create_embedding_provider,
    create_language_model_provider,
)
from app.ranking.reranker import LLMReranker
from app.ranking.scoring import CompositeRanker, RankingWeights
from app.repositories.search import PgVectorSearchRepository, SqlAlchemyStructuredSearchRepository
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.intent import IntentParser
from app.retrieval.metadata_grounding import SearchVocabulary
from app.retrieval.protocols import GraphSearchRepository
from app.services.embeddings import EmbeddingService
from app.services.search import SearchService

SessionDependency = Annotated[AsyncSession, Depends(get_database_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


async def get_search_service(
    session: SessionDependency,
    settings: SettingsDependency,
) -> AsyncIterator[SearchService]:
    try:
        embedding_provider = create_embedding_provider(settings)
        llm_provider = create_language_model_provider(settings)
    except ProviderConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    async with (
        embedding_provider,
        llm_provider,
    ):
        vocabulary = SearchVocabulary(
            cities=tuple(
                await session.scalars(
                    select(PersonModel.location)
                    .where(PersonModel.location.is_not(None))
                    .distinct()
                    .limit(200)
                )
            ),
            countries=tuple(
                await session.scalars(
                    select(PersonModel.country)
                    .where(PersonModel.country.is_not(None))
                    .distinct()
                    .limit(200)
                )
            ),
            companies=tuple(
                await session.scalars(select(CompanyModel.name).distinct().limit(200))
            ),
            skills=tuple(await session.scalars(select(SkillModel.name).distinct().limit(300))),
            technologies=tuple(
                await session.scalars(select(TechnologyModel.name).distinct().limit(300))
            ),
            domains=tuple(await session.scalars(select(DomainModel.name).distinct().limit(200))),
        )
        weights = RankingWeights(
            semantic=settings.ranking_semantic_weight,
            skills=settings.ranking_skill_weight,
            domains=settings.ranking_domain_weight,
            experience=settings.ranking_experience_weight,
            graph=settings.ranking_graph_weight,
            location=settings.ranking_location_weight,
            preference=settings.ranking_preference_weight,
        )
        embedding_service = EmbeddingService(
            embedding_provider,
            expected_dimension=settings.embedding_dimension,
            batch_size=settings.embedding_batch_size,
        )
        retriever = HybridRetriever(
            structured_repository=SqlAlchemyStructuredSearchRepository(session),
            vector_repository=PgVectorSearchRepository(session),
            embedding_service=embedding_service,
            graph_repository=graph_repository,
            ranker=CompositeRanker(weights),
            reranker=LLMReranker(llm_provider),
            candidate_pool_size=settings.search_candidate_pool_size,
            minimum_score=settings.search_min_score,
            vector_limit=settings.vector_search_limit,
            graph_limit=settings.graph_search_limit,
            max_graph_hops=settings.max_graph_hops,
        )
        yield SearchService(
            intent_parser=IntentParser(llm_provider, vocabulary),
            retriever=retriever,
            answer_generator=EvidenceAnswerGenerator(llm_provider),
        )


SearchServiceDependency = Annotated[SearchService, Depends(get_search_service)]


@dataclass(frozen=True)
class ExternalHealth:
    redis: bool
    graph: bool


async def get_external_health() -> ExternalHealth:
    redis_ready = True
    graph_ready = True
    try:
        await redis_client.ping()
    except Exception:
        redis_ready = False
    try:
        await graph_repository.verify_connectivity()
    except Exception:
        graph_ready = False
    return ExternalHealth(redis=redis_ready, graph=graph_ready)


ExternalHealthDependency = Annotated[ExternalHealth, Depends(get_external_health)]


def get_graph_search_repository() -> GraphSearchRepository:
    return graph_repository


GraphRepositoryDependency = Annotated[
    GraphSearchRepository,
    Depends(get_graph_search_repository),
]
