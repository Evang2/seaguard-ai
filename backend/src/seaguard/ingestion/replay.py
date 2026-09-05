from __future__ import annotations

import csv
import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

SIMULATOR_MMSI_START = 990_000_001
SIMULATOR_MMSI_END = 999_999_999


@dataclass(frozen=True)
class ReplayRecord:
    """One source AIS row with a parsed source timestamp."""

    original_timestamp: datetime
    values: dict[str, str]


@dataclass(frozen=True)
class ReplaySource:
    """Loaded AIS replay source."""

    fieldnames: tuple[str, ...]
    records: tuple[ReplayRecord, ...]
    skipped_invalid_timestamps: int = 0

    @property
    def first_timestamp(self) -> datetime:
        return self.records[0].original_timestamp

    @property
    def last_timestamp(self) -> datetime:
        return self.records[-1].original_timestamp

    @property
    def span_seconds(self) -> float:
        return (self.last_timestamp - self.first_timestamp).total_seconds()


@dataclass(frozen=True)
class ReplayBatch:
    """A batch of source AIS rows emitted together."""

    sequence: int
    bucket_index: int
    source_offset_seconds: float
    records: tuple[ReplayRecord, ...]


def parse_ais_timestamp(value: str) -> datetime:
    """Parse an AIS timestamp and normalize it to UTC."""

    cleaned = value.strip()

    if not cleaned:
        raise ValueError("AIS timestamp is empty.")

    normalized = cleaned.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def format_ais_timestamp(value: datetime) -> str:
    """Serialize a timestamp in the format accepted by the clean CSV importer."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC).isoformat(
        sep=" ",
        timespec="seconds",
    )


def load_replay_source(
    path: Path,
    *,
    timestamp_column: str = "timestamp",
) -> ReplaySource:
    """Load and sort a clean AIS CSV for replay."""

    path = path.expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(f"Replay source does not exist: {path}")

    records: list[ReplayRecord] = []
    skipped_invalid_timestamps = 0

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError("Replay source does not contain a CSV header.")

        fieldnames = tuple(reader.fieldnames)

        if timestamp_column not in fieldnames:
            raise ValueError(
                f"Replay source is missing required column: {timestamp_column}"
            )

        if "mmsi" not in fieldnames:
            raise ValueError("Replay source is missing required column: mmsi")

        for row in reader:
            raw_timestamp = row.get(timestamp_column, "")

            try:
                parsed_timestamp = parse_ais_timestamp(raw_timestamp)
            except (TypeError, ValueError):
                skipped_invalid_timestamps += 1
                continue

            records.append(
                ReplayRecord(
                    original_timestamp=parsed_timestamp,
                    values=dict(row),
                )
            )

    if not records:
        raise ValueError("Replay source contains no rows with valid timestamps.")

    records.sort(key=lambda record: record.original_timestamp)

    return ReplaySource(
        fieldnames=fieldnames,
        records=tuple(records),
        skipped_invalid_timestamps=skipped_invalid_timestamps,
    )


def build_synthetic_mmsi_map(
    records: Sequence[ReplayRecord],
    *,
    first_synthetic_mmsi: int = SIMULATOR_MMSI_START,
) -> dict[str, str]:
    """
    Build a deterministic source-MMSI -> simulator-MMSI mapping.

    Source MMSIs are sorted before allocation, so a given source dataset always
    receives the same mapping. Synthetic MMSIs remain exactly nine digits to
    satisfy SeaGuard's importer contract.
    """

    source_mmsis = sorted(
        {
            record.values.get("mmsi", "").strip()
            for record in records
            if record.values.get("mmsi", "").strip()
        }
    )

    if not source_mmsis:
        raise ValueError("Replay source contains no MMSI values.")

    last_required = first_synthetic_mmsi + len(source_mmsis) - 1

    if first_synthetic_mmsi < 100_000_000 or last_required > SIMULATOR_MMSI_END:
        raise ValueError("Synthetic MMSI allocation must stay within nine digits.")

    return {
        source_mmsi: str(first_synthetic_mmsi + index)
        for index, source_mmsi in enumerate(source_mmsis)
    }


def iter_replay_batches(
    records: Sequence[ReplayRecord],
    *,
    batch_seconds: float,
) -> Iterator[ReplayBatch]:
    """Group sorted source rows into fixed-width source-time buckets."""

    if batch_seconds <= 0:
        raise ValueError("batch_seconds must be greater than 0.")

    if not records:
        return

    source_start = records[0].original_timestamp
    current_bucket: int | None = None
    current_records: list[ReplayRecord] = []
    sequence = 0

    for record in records:
        offset_seconds = (record.original_timestamp - source_start).total_seconds()
        bucket_index = int(offset_seconds // batch_seconds)

        if current_bucket is None:
            current_bucket = bucket_index

        if bucket_index != current_bucket:
            sequence += 1
            yield ReplayBatch(
                sequence=sequence,
                bucket_index=current_bucket,
                source_offset_seconds=(current_bucket * batch_seconds),
                records=tuple(current_records),
            )

            current_bucket = bucket_index
            current_records = []

        current_records.append(record)

    if current_records and current_bucket is not None:
        sequence += 1
        yield ReplayBatch(
            sequence=sequence,
            bucket_index=current_bucket,
            source_offset_seconds=(current_bucket * batch_seconds),
            records=tuple(current_records),
        )


def remap_timestamp(
    source_timestamp: datetime,
    *,
    source_start: datetime,
    simulation_start: datetime,
) -> datetime:
    """Move a source timestamp onto the simulation timeline without compression."""

    return simulation_start + (source_timestamp - source_start)


def remapped_batch_bounds(
    batch: ReplayBatch,
    *,
    source_start: datetime,
    simulation_start: datetime,
) -> tuple[datetime, datetime]:
    """Return first/last remapped AIS timestamps for a replay batch."""

    first = remap_timestamp(
        batch.records[0].original_timestamp,
        source_start=source_start,
        simulation_start=simulation_start,
    )
    last = remap_timestamp(
        batch.records[-1].original_timestamp,
        source_start=source_start,
        simulation_start=simulation_start,
    )

    return first, last


def write_replay_batch(
    batch: ReplayBatch,
    *,
    fieldnames: Sequence[str],
    output_directory: Path,
    source_start: datetime,
    simulation_start: datetime,
    timestamp_column: str = "timestamp",
    mmsi_map: Mapping[str, str] | None = None,
    file_prefix: str = "seaguard_sim",
) -> Path:
    """Write one simulated AIS batch atomically."""

    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    first_timestamp, _ = remapped_batch_bounds(
        batch,
        source_start=source_start,
        simulation_start=simulation_start,
    )

    timestamp_token = first_timestamp.strftime("%Y%m%dT%H%M%SZ")
    final_path = output_directory / (
        f"{file_prefix}_{batch.sequence:05d}_{timestamp_token}.csv"
    )
    temporary_path = output_directory / f".{final_path.name}.tmp"

    with temporary_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames),
            extrasaction="ignore",
        )
        writer.writeheader()

        for record in batch.records:
            output_row = dict(record.values)

            output_row[timestamp_column] = format_ais_timestamp(
                remap_timestamp(
                    record.original_timestamp,
                    source_start=source_start,
                    simulation_start=simulation_start,
                )
            )

            if mmsi_map is not None:
                source_mmsi = output_row.get("mmsi", "").strip()

                try:
                    output_row["mmsi"] = mmsi_map[source_mmsi]
                except KeyError as error:
                    raise ValueError(
                        f"No simulator MMSI mapping exists for source MMSI {source_mmsi!r}."
                    ) from error

            writer.writerow(output_row)

    os.replace(temporary_path, final_path)

    return final_path


def estimated_real_duration(
    source: ReplaySource,
    *,
    speed: float,
) -> timedelta:
    """Estimate wall-clock time required to replay the source."""

    if speed <= 0:
        raise ValueError("speed must be greater than 0.")

    return timedelta(seconds=(source.span_seconds / speed))
