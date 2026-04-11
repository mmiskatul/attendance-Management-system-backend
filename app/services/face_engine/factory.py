"""Face engine factory."""

from __future__ import annotations

from app.core.config import Settings
from app.services.face_engine.base import FaceEngine
from app.services.face_engine.insightface_engine import InsightFaceEngine
from app.services.face_engine.mock_engine import MockFaceEngine


def build_face_engine(settings: Settings) -> FaceEngine:
    """Instantiate the configured face engine provider."""

    provider = settings.face_engine_provider.lower()
    if provider == "insightface":
        return InsightFaceEngine(settings)
    return MockFaceEngine()
