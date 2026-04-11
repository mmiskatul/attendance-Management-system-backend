"""Deterministic mock face engine used for tests and local development."""

from __future__ import annotations

import hashlib

import numpy as np

from app.core.exceptions import ValidationAppError
from app.services.face_engine.base import DetectedFace, FaceEmbeddingVector
from app.utils.embeddings import normalize_embedding


class MockFaceEngine:
    """A lightweight deterministic engine that keeps the app runnable without ML dependencies."""

    provider_name = "mock"

    async def detect(self, image: np.ndarray) -> list[DetectedFace]:
        height, width = image.shape[:2]
        if height == 0 or width == 0:
            raise ValidationAppError("Image is empty.")
        return [DetectedFace(bbox=(0, 0, width, height), detection_score=0.99, pose="front", provider_payload=None)]

    async def embed(self, image: np.ndarray, face: DetectedFace | None = None) -> FaceEmbeddingVector:
        _ = face
        digest = hashlib.sha256(image.tobytes()).digest()
        raw = (digest * 32)[:512]
        vector = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        normalized = normalize_embedding(vector)
        return FaceEmbeddingVector(
            vector=normalized,
            model_name="mock-sha256",
            embedding_dim=int(normalized.shape[0]),
            pose="front",
            detection_score=0.99,
        )
