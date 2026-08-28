from datetime import UTC, datetime

from fastapi.testclient import TestClient

from seaguard.api.routes.playback import _as_utc
from seaguard.main import app

client = TestClient(app)


def test_playback_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])

    assert "/api/v1/playback/bounds" in paths
    assert "/api/v1/playback/snapshot" in paths


def test_playback_snapshot_requires_timestamp() -> None:
    response = client.get("/api/v1/playback/snapshot")

    assert response.status_code == 422


def test_playback_snapshot_validates_tolerance() -> None:
    response = client.get(
        "/api/v1/playback/snapshot",
        params={
            "at": "2024-06-14T12:00:00Z",
            "tolerance_minutes": 0,
        },
    )

    assert response.status_code == 422


def test_as_utc_adds_utc_to_naive_timestamp() -> None:
    value = datetime(
        2024,
        6,
        14,
        12,
        0,
        0,
    )

    result = _as_utc(value)

    assert result.tzinfo == UTC


def test_as_utc_preserves_utc_instant() -> None:
    value = datetime(
        2024,
        6,
        14,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    assert _as_utc(value) == value
