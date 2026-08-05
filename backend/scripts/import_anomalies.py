import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from seaguard.db.anomaly_importer import (
    import_anomaly_alerts_csv,
)
from seaguard.db.session import engine


def parse_arguments() -> argparse.Namespace:
    """Read command-line options."""

    parser = argparse.ArgumentParser(
        description=("Import generated anomaly alerts into PostgreSQL.")
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to the generated alert CSV.",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5_000,
        help="Number of CSV rows read per chunk.",
    )

    parser.add_argument(
        "--insert-batch-size",
        type=int,
        default=1_000,
        help="Number of alerts per SQL insert.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=None,
        help="Optional maximum number of rows.",
    )

    return parser.parse_args()


def main() -> None:
    """Import anomaly alerts."""

    arguments = parse_arguments()

    print(f"Source: {arguments.file.resolve()}")
    print(f"Chunk size: {arguments.chunk_size:,}")
    print(f"Insert batch size: {arguments.insert_batch_size:,}")

    with Session(engine) as session:
        summary = import_anomaly_alerts_csv(
            session,
            arguments.file,
            chunk_size=arguments.chunk_size,
            insert_batch_size=(arguments.insert_batch_size),
            maximum_rows=arguments.rows,
        )

    print()
    print("Alert import completed.")
    print(f"Rows read:           {summary.rows_read:,}")
    print(f"Rows imported:       {summary.rows_imported:,}")
    print(f"Rows rejected:       {summary.rows_rejected:,}")
    print(f"Messages not found:  {summary.messages_not_found:,}")
    print(f"Duplicates skipped:  {summary.duplicates_skipped:,}")


if __name__ == "__main__":
    main()
