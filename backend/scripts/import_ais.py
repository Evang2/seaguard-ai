import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from seaguard.db.ais_importer import (
    import_clean_ais_csv,
)
from seaguard.db.session import engine


def parse_arguments() -> argparse.Namespace:
    """Read command-line options."""

    parser = argparse.ArgumentParser(
        description=("Import a cleaned AIS CSV into PostgreSQL/PostGIS.")
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to the cleaned AIS CSV.",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5_000,
        help="Number of CSV rows read at a time.",
    )

    parser.add_argument(
        "--insert-batch-size",
        type=int,
        default=1_000,
        help="Number of AIS messages per SQL insert.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=None,
        help=("Optional maximum row count for a test import."),
    )

    return parser.parse_args()


def main() -> None:
    """Import a cleaned AIS file."""

    arguments = parse_arguments()

    print(f"Source: {arguments.file.resolve()}")
    print(f"Chunk size: {arguments.chunk_size:,}")
    print(f"Insert batch size: {arguments.insert_batch_size:,}")

    if arguments.rows is not None:
        print(f"Maximum rows: {arguments.rows:,}")

    with Session(engine) as session:
        summary = import_clean_ais_csv(
            session,
            arguments.file,
            chunk_size=arguments.chunk_size,
            insert_batch_size=(arguments.insert_batch_size),
            maximum_rows=arguments.rows,
        )

    print()
    print("Import completed.")
    print(f"Import job ID:       {summary.job_id}")
    print(f"Rows read:           {summary.rows_read:,}")
    print(f"Rows imported:       {summary.rows_imported:,}")
    print(f"Rows rejected:       {summary.rows_rejected:,}")
    print(f"Duplicates skipped:  {summary.duplicates_skipped:,}")


if __name__ == "__main__":
    main()
