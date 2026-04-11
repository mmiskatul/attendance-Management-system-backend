"""Integration tests for the embedded frontend."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_root_serves_frontend() -> None:
    app = create_app(startup_enabled=False)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "University Attendance Console" in response.text


def test_static_asset_serves() -> None:
    app = create_app(startup_enabled=False)
    client = TestClient(app)

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "handleLogin" in response.text
