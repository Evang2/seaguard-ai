import pandas as pd
import pytest

from seaguard.ais.trajectory import (
    build_trajectory_metrics,
)


def test_build_trajectory_metrics() -> None:
    """Trajectory metrics should use ordered consecutive positions."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:00:00Z",
                "latitude": 0.0,
                "longitude": 0.0,
                "sog": 10.0,
                "cog": 10.0,
                "heading": 10.0,
            },
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T01:00:00Z",
                "latitude": 0.0,
                "longitude": 1.0,
                "sog": 20.0,
                "cog": 350.0,
                "heading": 350.0,
            },
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T02:00:00Z",
                "latitude": 0.0,
                "longitude": 2.0,
                "sog": 20.0,
                "cog": 5.0,
                "heading": 5.0,
            },
        ]
    )

    trajectory = build_trajectory_metrics(source)

    assert len(trajectory) == 3

    assert pd.isna(trajectory.loc[0, "distance_nm"])

    assert trajectory.loc[1, "distance_nm"] == pytest.approx(
        60.04,
        rel=0.001,
    )

    assert trajectory.loc[1, "calculated_speed_knots"] == pytest.approx(
        60.04,
        rel=0.001,
    )

    assert trajectory.loc[2, "cumulative_distance_nm"] == pytest.approx(
        120.08,
        rel=0.001,
    )

    assert trajectory.loc[
        1,
        "acceleration_knots_per_minute",
    ] == pytest.approx(10 / 60)

    assert trajectory.loc[
        1,
        "course_change_degrees",
    ] == pytest.approx(20.0)

    assert trajectory.loc[
        2,
        "course_change_degrees",
    ] == pytest.approx(15.0)


def test_trajectory_requires_one_vessel() -> None:
    """Metrics should not mix observations from different vessels."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:00:00Z",
                "latitude": 36.9,
                "longitude": -76.3,
            },
            {
                "mmsi": "987654321",
                "timestamp": "2024-06-15T00:01:00Z",
                "latitude": 36.91,
                "longitude": -76.31,
            },
        ]
    )

    with pytest.raises(
        ValueError,
        match="exactly one MMSI",
    ):
        build_trajectory_metrics(source)


def test_trajectory_can_filter_mmsi() -> None:
    """The caller should be able to select one MMSI."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:00:00Z",
                "latitude": 36.9,
                "longitude": -76.3,
            },
            {
                "mmsi": "987654321",
                "timestamp": "2024-06-15T00:01:00Z",
                "latitude": 36.91,
                "longitude": -76.31,
            },
        ]
    )

    trajectory = build_trajectory_metrics(
        source,
        mmsi="123456789",
    )

    assert len(trajectory) == 1
    assert trajectory.iloc[0]["mmsi"] == "123456789"
