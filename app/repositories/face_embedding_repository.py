"""Face embedding repository."""

from __future__ import annotations

from bson.binary import Binary
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.face_embedding import FaceEmbeddingDocument
from app.repositories.base import MongoRepository


class FaceEmbeddingRepository(MongoRepository):
    """MongoDB repository for face embeddings."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["face_embeddings"]

    async def create_many(self, embeddings: list[FaceEmbeddingDocument]) -> list[FaceEmbeddingDocument]:
        if not embeddings:
            return []

        payloads = []
        for embedding in embeddings:
            payload = self.serialize_document(embedding.model_dump(by_alias=True, exclude_none=True))
            payload["embedding_binary"] = Binary(payload["embedding_binary"])
            payloads.append(payload)

        result = await self.collection.insert_many(payloads)
        documents: list[FaceEmbeddingDocument] = []
        for payload, inserted_id in zip(payloads, result.inserted_ids, strict=True):
            payload["_id"] = str(inserted_id)
            payload["embedding_binary"] = bytes(payload["embedding_binary"])
            documents.append(FaceEmbeddingDocument.model_validate(payload))
        return documents

    async def list_active_by_student(self, tenant_id: str, student_id: str) -> list[FaceEmbeddingDocument]:
        cursor = self.collection.find({"tenant_id": tenant_id, "student_id": student_id, "is_active": True})
        return [self._build_document(document) async for document in cursor]

    async def list_active_by_scope(
        self,
        tenant_id: str,
        campus_id: str,
        *,
        exclude_student_id: str | None = None,
    ) -> list[FaceEmbeddingDocument]:
        query = {"tenant_id": tenant_id, "campus_id": campus_id, "is_active": True}
        if exclude_student_id:
            query["student_id"] = {"$ne": exclude_student_id}
        cursor = self.collection.find(query)
        return [self._build_document(document) async for document in cursor]

    def _build_document(self, document: dict[str, object]) -> FaceEmbeddingDocument:
        normalized = self.normalize_document(document)
        assert normalized is not None
        normalized["embedding_binary"] = bytes(normalized["embedding_binary"])
        return FaceEmbeddingDocument.model_validate(normalized)
