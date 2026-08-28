from __future__ import annotations

import argparse
import time
from pathlib import Path

from seaguard.ingestion.directory import (
    DirectoryAISWatcher,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Watch a directory for stable incoming AIS CSV files.")
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
        help=("Number of unchanged scans required before a file is considered ready."),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.poll_seconds <= 0:
        raise SystemExit("--poll-seconds must be greater than 0.")

    directory = Path(args.directory).expanduser().resolve()

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    watcher = DirectoryAISWatcher(
        directory,
        required_stable_scans=args.stable_scans,
    )

    print(f"Watching AIS directory: {directory}")

    print("Press Ctrl+C to stop.")

    try:
        while True:
            ready_files = watcher.scan()

            for item in ready_files:
                print()
                print("AIS file ready")

                print(f"  name: {item.name}")

                print(f"  size: {item.size_bytes:,} bytes")

                print(f"  sha256: {item.sha256}")

            time.sleep(args.poll_seconds)

    except KeyboardInterrupt:
        print()
        print("AIS directory watcher stopped.")


if __name__ == "__main__":
    main()
