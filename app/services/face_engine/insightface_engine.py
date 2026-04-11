"""InsightFace-backed face engine provider."""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from app.core.config import Settings
from app.core.exceptions import ValidationAppError
from app.services.face_engine.base import DetectedFace, FaceEmbeddingVector
from app.utils.embeddings import normalize_embedding


class InsightFaceEngine:
    """InsightFace implementation with lazy model initialization."""

    provider_name = "insightface"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._app: Any | None = None

    def _get_app(self) -> Any:
        if self._app is None:
            from insightface.app import FaceAnalysis

            self._app = FaceAnalysis(name=self.settings.face_model_name, providers=["CPUExecutionProvider"])
            self._app.prepare(ctx_id=0, det_size=(640, 640))
        return self._app

    async def detect(self, image: np.ndarray) -> list[DetectedFace]:
        faces = await asyncio.to_thread(self._get_app().get, image)
        return [self._to_detected_face(face, image=image) for face in faces]

    async def embed(self, image: np.ndarray, face: DetectedFace | None = None) -> FaceEmbeddingVector:
        if face is None:
            faces = await self.detect(image)
            if len(faces) != 1:
                raise ValidationAppError("Exactly one face must be present to generate an embedding.")
            face = faces[0]

        provider_payload = face.provider_payload
        embedding = getattr(provider_payload, "embedding", None)
        if embedding is None:
            faces = await asyncio.to_thread(self._get_app().get, image)
            if not faces:
                raise ValidationAppError("Unable to generate embedding from image.")
            provider_payload = faces[0]
            embedding = provider_payload.embedding

        vector = normalize_embedding(np.asarray(embedding, dtype=np.float32))
        return FaceEmbeddingVector(
            vector=vector,
            model_name=self.settings.face_model_name,
            embedding_dim=int(vector.shape[0]),
            pose=face.pose,
            detection_score=face.detection_score,
        )

    def _to_detected_face(self, provider_face: Any, *, image: np.ndarray) -> DetectedFace:
        bbox_array = getattr(provider_face, "bbox", None)
        if bbox_array is None:
            height, width = image.shape[:2]
            bbox = (0, 0, width, height)
        else:
            x1, y1, x2, y2 = [int(value) for value in bbox_array.tolist()]
            bbox = (x1, y1, x2, y2)

        return DetectedFace(
            bbox=bbox,
            detection_score=float(getattr(provider_face, "det_score", 0.0)),
            pose=self._resolve_pose(provider_face),
            provider_payload=provider_face,
        )

    @staticmethod
    def _resolve_pose(provider_face: Any) -> str:
        pose = getattr(provider_face, "pose", None)
        if pose is None:
            return "front"
        values = [float(value) for value in pose.tolist()]
        if not values:
            return "front"
        vertical = values[0]
        horizontal = values[1] if len(values) > 1 else values[0]
        if horizontal >= 15:
            return "left"
        if horizontal <= -15:
            return "right"
        if vertical >= 15:
            return "up"
        if vertical <= -15:
            return "down"
        return "front"
