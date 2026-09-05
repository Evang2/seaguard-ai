from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path

from seaguard.ingestion.replay import (
    build_synthetic_mmsi_map,
    estimated_real_duration,
    iter_replay_batches,
    load_replay_source,
    parse_ais_timestamp,
    remapped_batch_bounds,
    write_replay_batch,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay a historical clean AIS CSV into SeaGuard's existing "
            "continuous-ingestion directory as a live-like feed."
        )
    )

    parser.add_argument(
        "source",
        nargs="?",
        default="../data/processed/ais_sample/ais_sample_clean.csv",
        help="Historical clean AIS CSV to replay.",
    )
    parser.add_argument(
        "--output-dir",
        default="../data/incoming",
        help="Directory watched by SeaGuard continuous ingestion.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=60.0,
        help=(
            "Replay speed multiplier. 60 means 60 seconds of source AIS time "
            "are delivered per 1 second of wall-clock time."
        ),
    )
    parser.add_argument(
        "--batch-seconds",
        type=float,
        default=300.0,
        help=(
            "Width of each source-time batch in seconds. Default 300 with "
            "--speed 60 emits about one batch every 5 real seconds."
        ),
    )
    parser.add_argument(
        "--start-at",
        default=None,
        help=(
            "Simulation timestamp corresponding to the first source AIS row. "
            "ISO-8601. Default: current UTC time."
        ),
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Stop after this many non-empty batches. Useful for smoke tests.",
    )
    parser.add_argument(
        "--prefix",
        default="seaguard_sim",
        help="Filename prefix for emitted CSV batches.",
    )
    parser.add_argument(
        "--preserve-mmsi",
        action="store_true",
        help=(
            "Keep original source MMSIs. By default the simulator remaps them "
            "to deterministic 99xxxxxxx identities so replayed vessels do not "
            "join historical trajectories already stored in SeaGuard."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the replay plan without writing or sleeping.",
    )

    return parser.parse_args()


def resolve_simulation_start(raw_value: str | None) -> datetime:
    if raw_value is None:
        return datetime.now(UTC).replace(microsecond=0)

    return parse_ais_timestamp(raw_value).replace(microsecond=0)


def sleep_until(target_monotonic: float) -> None:
    while True:
        remaining = target_monotonic - time.monotonic()

        if remaining <= 0:
            return

        time.sleep(min(remaining, 0.5))


def main() -> None:
    args = parse_args()

    if args.speed <= 0:
        raise SystemExit("--speed must be greater than 0.")

    if args.batch_seconds <= 0:
        raise SystemExit("--batch-seconds must be greater than 0.")

    if args.max_batches is not None and args.max_batches <= 0:
        raise SystemExit("--max-batches must be greater than 0.")

    source_path = Path(args.source).expanduser().resolve()
    output_directory = Path(args.output_dir).expanduser().resolve()

    source = load_replay_source(source_path)
    simulation_start = resolve_simulation_start(args.start_at)

    mmsi_map = None

    if not args.preserve_mmsi:
        mmsi_map = build_synthetic_mmsi_map(source.records)

    batches = iter_replay_batches(
        source.records,
        batch_seconds=args.batch_seconds,
    )

    if args.max_batches is not None:
        batches = islice(batches, args.max_batches)

    print("SeaGuard live AIS simulator")
    print(f"Source: {source_path}")
    print(f"Output directory: {output_directory}")
    print(f"Valid source rows: {len(source.records):,}")

    if source.skipped_invalid_timestamps:
        print(
            "Rows skipped because timestamp could not be scheduled: "
            f"{source.skipped_invalid_timestamps:,}"
        )

    print(
        "Source period: "
        f"{source.first_timestamp.isoformat()} -> "
        f"{source.last_timestamp.isoformat()}"
    )
    print(f"Source span: {source.span_seconds / 3600:.2f} hours")
    print(f"Replay speed: {args.speed:g}x")
    print(f"Source-time batch width: {args.batch_seconds:g}s")
    print(f"Nominal real batch cadence: {args.batch_seconds / args.speed:.2f}s")
    print(
        "Estimated complete replay duration: "
        f"{estimated_real_duration(source, speed=args.speed)}"
    )
    print(f"First simulated AIS timestamp: {simulation_start.isoformat()}")

    if mmsi_map is None:
        print("Vessel identity mode: original MMSIs preserved")
    else:
        synthetic_values = list(mmsi_map.values())
        print("Vessel identity mode: isolated synthetic MMSIs")
        print(f"Synthetic vessel identities: {len(mmsi_map):,}")
        print(
            "Synthetic MMSI range used: "
            f"{synthetic_values[0]} -> {synthetic_values[-1]}"
        )

    if args.max_batches is not None:
        print(f"Maximum batches: {args.max_batches}")

    print()
    print(
        "Important: replay speed changes delivery cadence only. "
        "AIS timestamp deltas are preserved so trajectory analytics "
        "remain physically meaningful."
    )

    if args.dry_run:
        print()
        print("Dry run; no files will be written.")

        planned = 0

        for batch in batches:
            first_timestamp, last_timestamp = remapped_batch_bounds(
                batch,
                source_start=source.first_timestamp,
                simulation_start=simulation_start,
            )

            planned += 1

            print(
                f"Batch {batch.sequence:05d}: "
                f"{len(batch.records):,} rows | "
                f"delivery +{batch.source_offset_seconds / args.speed:.2f}s | "
                f"AIS {first_timestamp.isoformat()} -> "
                f"{last_timestamp.isoformat()}"
            )

        print()
        print(f"Planned non-empty batches: {planned:,}")
        return

    print()
    print("Press Ctrl+C to stop.")

    wall_start = time.monotonic()
    emitted_rows = 0
    emitted_batches = 0

    try:
        for batch in batches:
            scheduled_wall_offset = batch.source_offset_seconds / args.speed
            sleep_until(wall_start + scheduled_wall_offset)

            path = write_replay_batch(
                batch,
                fieldnames=source.fieldnames,
                output_directory=output_directory,
                source_start=source.first_timestamp,
                simulation_start=simulation_start,
                mmsi_map=mmsi_map,
                file_prefix=args.prefix,
            )

            first_timestamp, last_timestamp = remapped_batch_bounds(
                batch,
                source_start=source.first_timestamp,
                simulation_start=simulation_start,
            )

            emitted_batches += 1
            emitted_rows += len(batch.records)

            print(
                f"[{emitted_batches:05d}] "
                f"{path.name} | "
                f"{len(batch.records):,} rows | "
                f"AIS {first_timestamp.isoformat()} -> "
                f"{last_timestamp.isoformat()}"
            )

    except KeyboardInterrupt:
        print()
        print("SeaGuard live AIS simulation stopped.")

    finally:
        print()
        print(f"Emitted {emitted_batches:,} batches / {emitted_rows:,} AIS rows.")


if __name__ == "__main__":
    main()
