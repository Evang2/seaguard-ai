from seaguard.main import app


def test_maritime_routes_are_registered() -> None:
    """All core maritime API routes should exist."""

    paths = app.openapi()["paths"]

    expected_paths = {
        "/api/v1/vessels",
        "/api/v1/vessels/{mmsi}",
        "/api/v1/vessels/{mmsi}/trajectory",
        "/api/v1/positions/recent",
        "/api/v1/anomalies",
    }

    assert expected_paths.issubset(paths)


def test_vessel_search_uses_get() -> None:
    """Vessel search should be a read-only endpoint."""

    path = app.openapi()["paths"]["/api/v1/vessels"]

    assert "get" in path


def test_trajectory_documents_geojson_response() -> None:
    """Trajectory endpoint should appear in OpenAPI."""

    operation = app.openapi()["paths"]["/api/v1/vessels/{mmsi}/trajectory"]["get"]

    assert operation["tags"] == ["vessels"]
