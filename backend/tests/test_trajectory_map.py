from pathlib import Path

import pandas as pd
import pytest

from seaguard.visualization.trajectory_map import (
    create_trajectory_map,
)


def test_create_trajectory_map(
    tmp_path: Path,
) -> None:
    """A valid trajectory should generate an HTML map."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:00:00Z",
                "latitude": 36.90,
                "longitude": -76.30,
                "sog": 10.0,
                "cog": 45.0,
                "heading": 44.0,
                "has_anomaly": False,
                "anomaly_count": 0,
                "anomaly_types": "",
            },
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:05:00Z",
                "latitude": 36.91,
                "longitude": -76.29,
                "sog": 11.0,
                "cog": 50.0,
                "heading": 49.0,
                "has_anomaly": True,
                "anomaly_count": 1,
                "anomaly_types": "position_jump",
            },
        ]
    )

    output_file = tmp_path / "trajectory_map.html"

    result = create_trajectory_map(
        source,
        output_file,
    )

    assert result == output_file.resolve()
    assert output_file.exists()

    html = output_file.read_text(encoding="utf-8")

    assert "123456789" in html
    assert "position_jump" in html
    assert "Vessel route" in html


def test_map_rejects_multiple_vessels(
    tmp_path: Path,
) -> None:
    """One map input should represent one vessel trajectory."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:00:00Z",
                "latitude": 36.90,
                "longitude": -76.30,
            },
            {
                "mmsi": "987654321",
                "timestamp": "2024-06-15T00:01:00Z",
                "latitude": 36.91,
                "longitude": -76.29,
            },
        ]
    )

    with pytest.raises(
        ValueError,
        match="exactly one MMSI",
    ):
        create_trajectory_map(
            source,
            tmp_path / "map.html",
        )


def test_map_requires_geographic_columns(
    tmp_path: Path,
) -> None:
    """The map should report missing core columns clearly."""

    source = pd.DataFrame(
        {
            "mmsi": ["123456789"],
            "timestamp": ["2024-06-15T00:00:00Z"],
        }
    )

    with pytest.raises(
        ValueError,
        match="latitude",
    ):
        create_trajectory_map(
            source,
            tmp_path / "map.html",
        )
