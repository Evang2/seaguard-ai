import argparse
import json
from pathlib import Path

import pandas as pd

from seaguard.ais.cleaning import clean_ais_dataframe

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "processed" / "ais_sample"


def parse_arguments() -> argparse.Namespace:
    """Read command-line options."""

    parser = argparse.ArgumentParser(
        description=(
            "Clean a NOAA AIS CSV and produce accepted, "
            "rejected, and quality-report files."
        )
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to the raw AIS CSV.",
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory for generated processed files.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=250_000,
        help=(
            "Maximum rows to process during this development stage. Default: 250000."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Clean the requested AIS CSV file."""

    arguments = parse_arguments()

    source_file = arguments.file.resolve()
    output_directory = arguments.output_directory.resolve()

    if not source_file.exists():
        raise FileNotFoundError(f"AIS source file does not exist: {source_file}")

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Reading: {source_file}")
    print(f"Maximum rows: {arguments.rows:,}")

    source = pd.read_csv(
        source_file,
        nrows=arguments.rows,
        low_memory=False,
    )

    cleaned, rejected, report = clean_ais_dataframe(source)

    source_stem = source_file.stem

    clean_file = output_directory / f"{source_stem}_clean.csv"

    rejected_file = output_directory / f"{source_stem}_rejected.csv"

    report_file = output_directory / f"{source_stem}_quality.json"

    cleaned.to_csv(
        clean_file,
        index=False,
    )

    rejected.to_csv(
        rejected_file,
        index=False,
    )

    report["source_file"] = str(source_file)
    report["row_limit"] = arguments.rows

    with report_file.open(
        mode="w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
        )

    print()
    print("Cleaning complete.")
    print(f"Rows read:       {report['rows_read']:,}")
    print(f"Rows clean:      {report['rows_clean']:,}")
    print(f"Rows rejected:   {report['rows_rejected']:,}")
    print(f"Duplicates:     {report['duplicates_removed']:,}")
    print(f"Unique vessels: {report['unique_mmsi_clean']:,}")

    print()
    print(f"Clean file:    {clean_file}")
    print(f"Rejected file: {rejected_file}")
    print(f"Quality report:{report_file}")


if __name__ == "__main__":
    main()
