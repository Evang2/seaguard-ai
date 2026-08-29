from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from seaguard.ingestion.analytics import IngestionAnalyticsContext
from seaguard.ingestion.live_anomalies import (
    _filter_alerts_to_keys,
    _source_message_keys,
    build_live_motion_features,
)


def test_build_live_motion_features_stays_inside_vessel() -> None:
    start = datetime(
        2026,
        8,
        29,
        12,
        0,
        tzinfo=UTC,
    )

    dataframe = pd.DataFrame(
        [
            {
                "id": 1,
                "mmsi": "111111111",
                "timestamp": start,
                "latitude": 40.7000,
                "longitude": -74.0100,
                "sog": 10.0,
                "cog": 359.0,
                "heading": 359.0,
            },
            {
                "id": 2,
                "mmsi": "222222222",
                "timestamp": start,
                "latitude": 41.0000,
                "longitude": -73.0000,
                "sog": 4.0,
                "cog": 90.0,
                "heading": 90.0,
            },
            {
                "id": 3,
                "mmsi": "111111111",
                "timestamp": (start + timedelta(minutes=1)),
                "latitude": 40.7010,
                "longitude": -74.0090,
                "sog": 11.0,
                "cog": 1.0,
                "heading": 1.0,
            },
        ]
    )

    features = build_live_motion_features(dataframe)

    vessel_a = features.loc[features["mmsi"] == "111111111"].reset_index(drop=True)

    vessel_b = features.loc[features["mmsi"] == "222222222"].reset_index(drop=True)

    assert pd.isna(
        vessel_a.loc[
            0,
            "elapsed_seconds",
        ]
    )

    assert (
        vessel_a.loc[
            1,
            "elapsed_seconds",
        ]
        == 60.0
    )

    assert (
        vessel_a.loc[
            1,
            "course_change_degrees",
        ]
        == 2.0
    )

    assert (
        vessel_a.loc[
            1,
            "heading_change_degrees",
        ]
        == 2.0
    )

    assert pd.isna(
        vessel_b.loc[
            0,
            "elapsed_seconds",
        ]
    )


def test_nonpositive_interval_is_marked() -> None:
    timestamp = datetime(
        2026,
        8,
        29,
        12,
        0,
        tzinfo=UTC,
    )

    dataframe = pd.DataFrame(
        [
            {
                "id": 1,
                "mmsi": "111111111",
                "timestamp": timestamp,
                "latitude": 40.7000,
                "longitude": -74.0100,
                "sog": 10.0,
                "cog": 90.0,
                "heading": 90.0,
            },
            {
                "id": 2,
                "mmsi": "111111111",
                "timestamp": timestamp,
                "latitude": 40.7001,
                "longitude": -74.0099,
                "sog": 11.0,
                "cog": 91.0,
                "heading": 91.0,
            },
        ]
    )

    features = build_live_motion_features(dataframe)

    assert not bool(
        features.loc[
            0,
            "nonpositive_time_interval",
        ]
    )

    assert bool(
        features.loc[
            1,
            "nonpositive_time_interval",
        ]
    )


def test_source_message_keys_normalizes_csv(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incoming.csv"

    source.write_text(
        (
            "mmsi,timestamp,latitude,longitude\n"
            "999111222,2026-08-29T12:00:00Z,40.7,-74.0\n"
            "999111222.0,2026-08-29T12:01:00Z,40.7,-74.0\n"
            "bad,not-a-date,40.7,-74.0\n"
        ),
        encoding="utf-8",
    )

    keys = _source_message_keys(source)

    assert keys == {
        (
            "999111222",
            datetime(
                2026,
                8,
                29,
                12,
                0,
                tzinfo=UTC,
            ),
        ),
        (
            "999111222",
            datetime(
                2026,
                8,
                29,
                12,
                1,
                tzinfo=UTC,
            ),
        ),
    }


def test_filter_alerts_to_current_import_only() -> None:
    timestamp_a = datetime(
        2026,
        8,
        29,
        12,
        0,
        tzinfo=UTC,
    )

    timestamp_b = datetime(
        2026,
        8,
        29,
        12,
        1,
        tzinfo=UTC,
    )

    alerts = pd.DataFrame(
        [
            {
                "mmsi": "999111222",
                "timestamp": timestamp_a,
                "anomaly_type": "reporting_gap",
            },
            {
                "mmsi": "999111222",
                "timestamp": timestamp_b,
                "anomaly_type": "speed_mismatch",
            },
        ]
    )

    filtered = _filter_alerts_to_keys(
        alerts,
        {
            (
                "999111222",
                timestamp_b,
            )
        },
    )

    assert len(filtered) == 1

    assert filtered.iloc[0]["anomaly_type"] == "speed_mismatch"


def test_context_type_is_stable() -> None:
    context = IngestionAnalyticsContext(
        job_id=12,
        source_file=Path("/tmp/incoming.csv"),
        rows_read=3,
        rows_imported=3,
        rows_rejected=0,
        duplicates_skipped=0,
    )

    assert context.rows_imported == 3
