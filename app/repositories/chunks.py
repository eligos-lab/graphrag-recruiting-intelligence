from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.database.models import (
    DocumentChunkModel,
    PersonModel,
    RawDocumentModel,
)
from app.ingestion.chunking import ResumeChunk


@dataclass(frozen=True)
class ChunkingContext:
    document_id: UUID
    person_id: UUID
    source: str
    external_id: str
    document_type: str
    raw_text: str
    metadata: dict[str, Any]
    company_ids: dict[str, UUID]


class ChunkPersistOutcome(StrEnum):
    CREATED = "created"
    UPDATED = "updated"


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_structured_contexts(self, *, limit: int | None = None) -> list[ChunkingContext]:
        statement = (
            select(RawDocumentModel)
            .where(
                RawDocumentModel.person_id.is_not(None),
                RawDocumentModel.document_type.in_(("csv", "json")),
            )
            .options(selectinload(RawDocumentModel.person).selectinload(PersonModel.companies))
            .order_by(RawDocumentModel.created_at, RawDocumentModel.id)
        )
        if limit is not None:
            statement = statement.limit(limit)

        documents = list(await self.session.scalars(statement))
        contexts: list[ChunkingContext] = []
        for document in documents:
            person = document.person
            if person is None:
                continue
            contexts.append(
                ChunkingContext(
                    document_id=document.id,
                    person_id=person.id,
                    source=document.source,
                    external_id=document.external_id,
                    document_type=document.document_type,
                    raw_text=document.raw_text,
                    metadata=document.document_metadata,
                    company_ids={
                        company.normalized_name: company.id for company in person.companies
                    },
                )
            )
        return contexts

    async def is_current(
        self,
        document_id: UUID,
        chunks: list[ResumeChunk],
        embedding_model: str,
        embedding_dimension: int,
    ) -> bool:
        stored = list(
            await self.session.scalars(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.document_id == document_id)
                .order_by(DocumentChunkModel.ordinal)
            )
        )
        if len(stored) != len(chunks):
            return False
        return all(
            model.ordinal == chunk.ordinal
            and model.content_checksum == chunk.content_checksum
            and model.embedding_model == embedding_model
            and len(model.embedding) == embedding_dimension
            for model, chunk in zip(stored, chunks, strict=True)
        )

    async def upsert(
        self,
        chunks: list[ResumeChunk],
        embeddings: list[list[float]],
        embedding_model: str,
    ) -> ChunkPersistOutcome:
        if not chunks:
            raise ValueError("At least one chunk is required")
        if len(chunks) != len(embeddings):
            raise ValueError("Chunk and embedding counts must match")

        document_id = chunks[0].document_id
        stored = list(
            await self.session.scalars(
                select(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
            )
        )
        by_ordinal = {model.ordinal: model for model in stored}
        expected_ordinals: set[int] = set()

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            if chunk.document_id != document_id:
                raise ValueError("All chunks must belong to the same document")
            expected_ordinals.add(chunk.ordinal)
            model = by_ordinal.get(chunk.ordinal)
            if model is None:
                model = DocumentChunkModel(document_id=document_id, ordinal=chunk.ordinal)
                self.session.add(model)
            model.person_id = chunk.person_id
            model.section = chunk.section.value
            model.content = chunk.content
            model.content_checksum = chunk.content_checksum
            model.embedding = embedding
            model.embedding_model = embedding_model
            model.chunk_metadata = chunk.metadata

        for ordinal, model in by_ordinal.items():
            if ordinal not in expected_ordinals:
                await self.session.delete(model)

        await self.session.flush()
        return ChunkPersistOutcome.UPDATED if stored else ChunkPersistOutcome.CREATED
