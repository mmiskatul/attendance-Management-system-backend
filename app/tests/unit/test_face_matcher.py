"""Tests for face matching."""

import numpy as np

from app.services.face_matcher import FaceMatcher, GalleryEmbedding


def test_face_matcher_returns_best_candidate() -> None:
    matcher = FaceMatcher()
    query = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    gallery = [
        GalleryEmbedding(
            embedding_id="emb-1",
            student_id="STU-001",
            vector=np.array([0.9, 0.1, 0.0], dtype=np.float32),
            pose="front",
            quality_score=0.9,
            model_name="test",
        ),
        GalleryEmbedding(
            embedding_id="emb-2",
            student_id="STU-002",
            vector=np.array([0.0, 1.0, 0.0], dtype=np.float32),
            pose="front",
            quality_score=0.9,
            model_name="test",
        ),
    ]

    match = matcher.find_best_match(query, gallery)
    assert match is not None
    assert match.student_id == "STU-001"
    assert match.embedding_id == "emb-1"
    assert match.confidence > 0.9
