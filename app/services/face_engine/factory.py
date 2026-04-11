"""Face engine factory."""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ValidationAppError
from app.services.face_engine.base import FaceEngine
from app.services.face_engine.mock_engine import MockFaceEngine


def build_face_engine(settings: Settings) -> FaceEngine:
    """Instantiate the configured face engine provider."""

    provider = settings.face_engine_provider.lower()
    if provider == "insightface":
        try:
            from app.services.face_engine.insightface_engine import InsightFaceEngine
        except ModuleNotFoundError as exc:
            raise ValidationAppError(
                "FACE_ENGINE_PROVIDER=insightface requires ML dependencies that are not installed. "
                "Install requirements-ml.txt/requirements-full.txt or switch the provider."
            ) from exc
        return InsightFaceEngine(settings)
    return MockFaceEngine()
