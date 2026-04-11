"""Face matching service."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.utils.embeddings import normalize_embedding


@dataclass(slots=True)
class GalleryEmbedding:
    """A cached embedding used during matching."""

    embedding_id: str
    student_id: str
    vector: np.ndarray
    pose: str | None
    quality_score: float
    model_name: str


@dataclass(slots=True)
class MatchCandidate:
    """Best match result."""

    embedding_id: str
    student_id: str
    confidence: float
    cosine_similarity: float
    pose: str | None


class FaceMatcher:
    """Vector matcher using cosine similarity."""

    @staticmethod
    def find_best_match(query_vector: np.ndarray, gallery: list[GalleryEmbedding]) -> MatchCandidate | None:
        if not gallery:
            return None

        normalized_query = normalize_embedding(query_vector)
        matrix = np.stack([normalize_embedding(item.vector) for item in gallery], axis=0)
        similarities = matrix @ normalized_query
        index = int(np.argmax(similarities))
        similarity = float(similarities[index])
        confidence = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
        best = gallery[index]
        return MatchCandidate(
            embedding_id=best.embedding_id,
            student_id=best.student_id,
            confidence=round(confidence, 4),
            cosine_similarity=round(similarity, 4),
            pose=best.pose,
        )
