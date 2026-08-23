from seaguard.main import app


def test_collision_routes_are_registered() -> None:
    paths = set(app.openapi()["paths"])

    assert "/api/v1/collisions" in paths

    assert "/api/v1/collisions/summary" in paths

    assert "/api/v1/collisions/{mmsi}" in paths
