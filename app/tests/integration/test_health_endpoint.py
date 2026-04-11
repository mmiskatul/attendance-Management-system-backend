"""Integration-style health endpoint test."""

from fastapi.testclient import TestClient

from app.db.dependencies import get_health_service
from app.main import create_app


class FakeHealthService:
    async def check(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "University Attendance Management API",
            "version": "1.0.0",
            "checks": {
                "database": "ok",
                "rate_limiter": "ok",
                "face_engine_provider": "mock",
            },
        }


def test_health_endpoint_returns_service_state() -> None:
    app = create_app(startup_enabled=False)
    app.dependency_overrides[get_health_service] = lambda: FakeHealthService()

    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["database"] == "ok"
