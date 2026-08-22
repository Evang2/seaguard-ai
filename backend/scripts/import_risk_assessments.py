import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from seaguard.db.risk_importer import (
    DEFAULT_ASSESSMENT_VERSION,
    import_risk_assessments_csv,
)
from seaguard.db.session import engine


def parse_arguments() -> argparse.Namespace:
    """Read command-line options."""

    parser = argparse.ArgumentParser(
        description=("Import SeaGuard hybrid risk assessments into PostgreSQL.")
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to ais_hybrid_risk.csv.",
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
        help="Number of risk assessments per SQL upsert.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=None,
        help="Optional maximum row count for a test import.",
    )

    parser.add_argument(
        "--assessment-version",
        type=str,
        default=DEFAULT_ASSESSMENT_VERSION,
        help="Version label stored with imported assessments.",
    )

    return parser.parse_args()


def main() -> None:
    """Import a hybrid risk CSV."""

    arguments = parse_arguments()

    print(f"Source: {arguments.file.resolve()}")
    print(f"Chunk size: {arguments.chunk_size:,}")
    print(f"Insert batch size: {arguments.insert_batch_size:,}")
    print(f"Assessment version: {arguments.assessment_version}")

    if arguments.rows is not None:
        print(f"Maximum rows: {arguments.rows:,}")

    with Session(engine) as session:
        summary = import_risk_assessments_csv(
            session,
            arguments.file,
            chunk_size=arguments.chunk_size,
            insert_batch_size=arguments.insert_batch_size,
            maximum_rows=arguments.rows,
            assessment_version=arguments.assessment_version,
        )

    print()
    print("Risk import completed.")
    print(f"Rows read:              {summary.rows_read:,}")
    print(f"Rows imported/upserted: {summary.rows_imported:,}")
    print(f"Rows rejected:          {summary.rows_rejected:,}")
    print(f"AIS messages not found: {summary.messages_not_found:,}")


if __name__ == "__main__":
    main()
