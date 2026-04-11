"""Face engine provider contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


@dataclass(slots=True)
class DetectedFace:
    """Detected face result."""

    bbox: tuple[int, int, int, int]
    detection_score: float
    pose: str | None = None
    provider_payload: Any = None


@dataclass(slots=True)
class FaceEmbeddingVector:
    """Generated face embedding."""

    vector: np.ndarray
    model_name: str
    embedding_dim: int
    pose: str | None = None
    detection_score: float = 1.0


class FaceEngine(Protocol):
    """Face engine abstraction."""

    provider_name: str

    async def detect(self, image: np.ndarray) -> list[DetectedFace]:
        """Detect faces in an image."""

    async def embed(self, image: np.ndarray, face: DetectedFace | None = None) -> FaceEmbeddingVector:
        """Generate an embedding for a detected face."""
