import os

import pytest
from fastapi.testclient import TestClient

from seaguard.main import app

client = TestClient(app)


def test_root_endpoint() -> None:
    """The root endpoint should return API metadata."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "SeaGuard AI API",
        "version": "0.1.0",
        "documentation": "/docs",
    }


def test_application_health_endpoint() -> None:
    """The application health endpoint should confirm FastAPI is running."""

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "seaguard-api",
    }


@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="Database integration tests are disabled.",
)
def test_database_health_endpoint() -> None:
    """The database health endpoint should confirm PostGIS is available."""

    response = client.get("/api/v1/health/database")

    assert response.status_code == 200

    response_body = response.json()

    assert response_body["status"] == "ok"
    assert response_body["database"] == "seaguard"
    assert isinstance(response_body["postgis"], str)
    assert response_body["postgis"]
