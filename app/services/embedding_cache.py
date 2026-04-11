"""Active embedding cache."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.repositories.face_embedding_repository import FaceEmbeddingRepository
from app.services.face_matcher import GalleryEmbedding
from app.utils.embeddings import binary_to_embedding


@dataclass(slots=True)
class CacheEntry:
    """Cached embedding scope."""

    embeddings: list[GalleryEmbedding]
    expires_at: float


class EmbeddingCache:
    """Cache active embeddings by tenant and campus."""

    def __init__(self, repository: FaceEmbeddingRepository, ttl_seconds: int) -> None:
        self.repository = repository
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, CacheEntry] = {}

    def _key(self, tenant_id: str, campus_id: str) -> str:
        return f"{tenant_id}:{campus_id}"

    async def get_scope_embeddings(self, tenant_id: str, campus_id: str) -> list[GalleryEmbedding]:
        key = self._key(tenant_id, campus_id)
        now = time.monotonic()
        entry = self._cache.get(key)
        if entry and entry.expires_at > now:
            return entry.embeddings

        documents = await self.repository.list_active_by_scope(tenant_id, campus_id)
        embeddings = [
            GalleryEmbedding(
                embedding_id=document.id or "",
                student_id=document.student_id,
                vector=binary_to_embedding(document.embedding_binary, document.embedding_dim),
                pose=document.pose,
                quality_score=document.quality_score,
                model_name=document.model_name,
            )
            for document in documents
        ]
        self._cache[key] = CacheEntry(embeddings=embeddings, expires_at=now + self.ttl_seconds)
        return embeddings

    def invalidate_scope(self, tenant_id: str, campus_id: str) -> None:
        self._cache.pop(self._key(tenant_id, campus_id), None)
