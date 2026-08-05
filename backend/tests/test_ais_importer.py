import pandas as pd

from seaguard.db.ais_importer import (
    _build_message_records,
    _build_vessel_records,
    _prepare_import_chunk,
)


def test_prepare_import_chunk_rejects_invalid_rows() -> None:
    """Invalid core AIS records should be rejected."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2026-07-01T10:00:00Z",
                "latitude": 37.98,
                "longitude": 23.72,
            },
            {
                "mmsi": "invalid",
                "timestamp": "not-a-date",
                "latitude": 100.0,
                "longitude": 23.72,
            },
        ]
    )

    prepared, rejected_count = _prepare_import_chunk(source)

    assert len(prepared) == 1
    assert rejected_count == 1
    assert prepared.iloc[0]["mmsi"] == "123456789"


def test_build_vessel_records_aggregates_dates() -> None:
    """Vessel metadata should cover the chunk time range."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": pd.Timestamp("2026-07-01T10:00:00Z"),
                "vessel_name": "SEA TEST",
                "call_sign": "TEST1",
            },
            {
                "mmsi": "123456789",
                "timestamp": pd.Timestamp("2026-07-01T11:00:00Z"),
                "vessel_name": "SEA TEST",
                "call_sign": "TEST1",
            },
        ]
    )

    records = _build_vessel_records(source)

    assert len(records) == 1
    assert records[0]["mmsi"] == "123456789"
    assert records[0]["name"] == "SEA TEST"
    assert records[0]["call_sign"] == "TEST1"

    assert (
        records[0]["first_seen"] == pd.Timestamp("2026-07-01T10:00:00Z").to_pydatetime()
    )

    assert (
        records[0]["last_seen"] == pd.Timestamp("2026-07-01T11:00:00Z").to_pydatetime()
    )


def test_build_message_records_creates_postgis_point() -> None:
    """AIS rows should become WGS 84 geographic points."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": pd.Timestamp("2026-07-01T10:00:00Z"),
                "latitude": 37.9838,
                "longitude": 23.7275,
                "sog": 12.5,
                "sog_unavailable": False,
            }
        ]
    )

    records = _build_message_records(
        source,
        vessel_ids={"123456789": 42},
    )

    assert len(records) == 1

    record = records[0]

    assert record["vessel_id"] == 42
    assert record["latitude"] == 37.9838
    assert record["longitude"] == 23.7275
    assert record["position"].srid == 4326
    assert record["position"].data == ("POINT(23.7275 37.9838)")
