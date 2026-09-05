from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta

from seaguard.ingestion.replay import (
    ReplayRecord,
    build_synthetic_mmsi_map,
    iter_replay_batches,
    load_replay_source,
    remap_timestamp,
    write_replay_batch,
)


def _record(
    timestamp: datetime,
    *,
    mmsi: str = "111000111",
) -> ReplayRecord:
    return ReplayRecord(
        original_timestamp=timestamp,
        values={
            "mmsi": mmsi,
            "timestamp": timestamp.isoformat(sep=" "),
            "latitude": "40.7000",
            "longitude": "-74.0000",
            "sog": "10.0",
            "cog": "90.0",
        },
    )


def test_replay_batches_preserve_source_time_gaps() -> None:
    start = datetime(2024, 6, 14, 0, 0, tzinfo=UTC)

    records = (
        _record(start),
        _record(start + timedelta(seconds=120)),
        _record(start + timedelta(seconds=620)),
    )

    batches = list(iter_replay_batches(records, batch_seconds=300))

    assert len(batches) == 2
    assert batches[0].source_offset_seconds == 0
    assert len(batches[0].records) == 2
    assert batches[1].source_offset_seconds == 600
    assert len(batches[1].records) == 1


def test_remap_timestamp_preserves_relative_interval() -> None:
    source_start = datetime(2024, 6, 14, 0, 0, tzinfo=UTC)
    source_timestamp = source_start + timedelta(minutes=7, seconds=30)
    simulation_start = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    result = remap_timestamp(
        source_timestamp,
        source_start=source_start,
        simulation_start=simulation_start,
    )

    assert result - simulation_start == timedelta(minutes=7, seconds=30)


def test_build_synthetic_mmsi_map_is_deterministic_and_unique() -> None:
    start = datetime(2024, 6, 14, 0, 0, tzinfo=UTC)

    records = (
        _record(start, mmsi="368000170"),
        _record(start + timedelta(seconds=10), mmsi="227730770"),
        _record(start + timedelta(seconds=20), mmsi="368000170"),
    )

    mapping = build_synthetic_mmsi_map(records)

    assert mapping == {
        "227730770": "990000001",
        "368000170": "990000002",
    }
    assert len(set(mapping.values())) == len(mapping)
    assert all(len(value) == 9 and value.isdigit() for value in mapping.values())


def test_write_replay_batch_remaps_timestamp_and_mmsi(tmp_path) -> None:
    source_start = datetime(2024, 6, 14, 0, 0, tzinfo=UTC)
    simulation_start = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    records = (
        _record(source_start, mmsi="111000111"),
        _record(
            source_start + timedelta(minutes=2),
            mmsi="222000222",
        ),
    )

    batch = next(iter_replay_batches(records, batch_seconds=300))
    mmsi_map = {
        "111000111": "990000001",
        "222000222": "990000002",
    }

    path = write_replay_batch(
        batch,
        fieldnames=(
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
            "sog",
            "cog",
        ),
        output_directory=tmp_path,
        source_start=source_start,
        simulation_start=simulation_start,
        mmsi_map=mmsi_map,
    )

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["mmsi"] for row in rows] == [
        "990000001",
        "990000002",
    ]
    assert rows[0]["timestamp"] == "2026-09-05 12:00:00+00:00"
    assert rows[1]["timestamp"] == "2026-09-05 12:02:00+00:00"
    assert rows[0]["latitude"] == "40.7000"
    assert rows[0]["longitude"] == "-74.0000"
    assert rows[0]["sog"] == "10.0"
    assert rows[0]["cog"] == "90.0"


def test_write_replay_batch_can_preserve_original_mmsi(tmp_path) -> None:
    source_start = datetime(2024, 6, 14, 0, 0, tzinfo=UTC)
    simulation_start = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    records = (_record(source_start, mmsi="111000111"),)
    batch = next(iter_replay_batches(records, batch_seconds=300))

    path = write_replay_batch(
        batch,
        fieldnames=(
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
            "sog",
            "cog",
        ),
        output_directory=tmp_path,
        source_start=source_start,
        simulation_start=simulation_start,
        mmsi_map=None,
    )

    with path.open("r", encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))

    assert row["mmsi"] == "111000111"


def test_load_replay_source_sorts_rows_and_skips_bad_timestamps(tmp_path) -> None:
    source = tmp_path / "source.csv"

    source.write_text(
        "\n".join(
            [
                "mmsi,timestamp,latitude,longitude",
                "1,2024-06-14 00:05:00+00:00,40.7,-74.0",
                "2,not-a-time,40.7,-74.0",
                "3,2024-06-14 00:01:00+00:00,40.7,-74.0",
            ]
        ),
        encoding="utf-8",
    )

    loaded = load_replay_source(source)

    assert loaded.skipped_invalid_timestamps == 1
    assert [record.values["mmsi"] for record in loaded.records] == [
        "3",
        "1",
    ]
