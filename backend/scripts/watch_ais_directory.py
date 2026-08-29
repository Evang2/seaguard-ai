from __future__ import annotations

import argparse
import time
from pathlib import Path

from seaguard.db.session import (
    SessionFactory,
)
from seaguard.ingestion.directory import (
    DirectoryAISWatcher,
)
from seaguard.ingestion.pipeline import (
    run_live_analytics,
)
from seaguard.ingestion.worker import (
    process_discovered_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Continuously ingest stable AIS CSV files into SeaGuard.")
    )

    parser.add_argument(
        "directory",
        nargs="?",
        default="../data/incoming",
        help=("Directory containing incoming AIS CSV files."),
    )

    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=2.0,
        help=("Seconds between directory scans."),
    )

    parser.add_argument(
        "--stable-scans",
        type=int,
        default=2,
        help=("Number of unchanged scans required before a file is processed."),
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5_000,
        help=("CSV rows read per importer chunk."),
    )

    parser.add_argument(
        "--insert-batch-size",
        type=int,
        default=1_000,
        help=("AIS rows inserted per database batch."),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be greater than 0.")

    if args.chunk_size <= 0:
        raise SystemExit("--chunk-size must be greater than 0.")

    if args.insert_batch_size <= 0:
        raise SystemExit("--insert-batch-size must be greater than 0.")

    directory = Path(args.directory).expanduser().resolve()

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    watcher = DirectoryAISWatcher(
        directory,
        required_stable_scans=(args.stable_scans),
    )

    print("SeaGuard continuous AIS ingestion")

    print(f"Incoming directory: {directory}")

    print(f"Poll interval: {args.poll_seconds}s")

    print("Press Ctrl+C to stop.")

    try:
        while True:
            ready_files = watcher.scan()

            for discovered in ready_files:
                print()
                print(f"Detected: {discovered.name}")

                print(f"SHA-256: {discovered.sha256}")

                try:
                    with SessionFactory() as session:
                        outcome = process_discovered_file(
                            session,
                            discovered,
                            chunk_size=(args.chunk_size),
                            insert_batch_size=(args.insert_batch_size),
                            analytics_runner=run_live_analytics,
                        )

                except Exception as error:
                    print(f"Import failed: {discovered.name}")

                    print(f"Reason: {error}")

                    continue

                if outcome.action == "skipped":
                    print("Already imported; skipping.")

                    print(f"Import job: {outcome.job_id}")

                    continue

                print("Import completed.")

                print(f"Import job: {outcome.job_id}")

                print(f"Rows read: {outcome.rows_read:,}")

                print(f"Rows imported: {outcome.rows_imported:,}")

                print(f"Rows rejected: {outcome.rows_rejected:,}")

                print(f"Duplicates skipped: {outcome.duplicates_skipped:,}")

            time.sleep(args.poll_seconds)

    except KeyboardInterrupt:
        print()
        print("SeaGuard AIS ingestion stopped.")


if __name__ == "__main__":
    main()
