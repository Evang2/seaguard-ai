import argparse
from pathlib import Path

import pandas as pd


def parse_arguments() -> argparse.Namespace:
    """Read the AIS file path from the terminal."""

    parser = argparse.ArgumentParser(description="Inspect an AIS CSV dataset.")

    parser.add_argument(
        "file",
        type=Path,
        help="Path to the AIS CSV file.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=100_000,
        help="Maximum number of rows to inspect.",
    )

    return parser.parse_args()


def inspect_ais_file(file_path: Path, row_limit: int) -> None:
    """Load part of an AIS CSV and print a basic data report."""

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"Reading file: {file_path}")
    print(f"Maximum rows: {row_limit:,}")

    dataframe = pd.read_csv(
        file_path,
        nrows=row_limit,
        low_memory=False,
    )

    print("\n=== DATASET SIZE ===")
    print(f"Rows loaded: {len(dataframe):,}")
    print(f"Columns: {len(dataframe.columns):,}")

    print("\n=== COLUMN NAMES ===")

    for number, column in enumerate(dataframe.columns, start=1):
        print(f"{number}. {column}")

    print("\n=== FIRST FIVE ROWS ===")
    print(dataframe.head().to_string())

    print("\n=== DATA TYPES ===")
    print(dataframe.dtypes.to_string())

    print("\n=== MISSING VALUES ===")

    missing_values = pd.DataFrame(
        {
            "missing_count": dataframe.isna().sum(),
            "missing_percent": dataframe.isna().mean() * 100,
        }
    ).sort_values(
        by="missing_percent",
        ascending=False,
    )

    print(missing_values.to_string(float_format=lambda value: f"{value:.2f}"))

    print("\n=== DUPLICATE ROWS ===")
    print(f"Duplicates: {dataframe.duplicated().sum():,}")

    if "MMSI" in dataframe.columns:
        print("\n=== VESSELS ===")
        print(f"Unique MMSI values: {dataframe['MMSI'].nunique(dropna=True):,}")

    if "BaseDateTime" in dataframe.columns:
        print("\n=== TIME RANGE ===")

        timestamps = pd.to_datetime(
            dataframe["BaseDateTime"],
            errors="coerce",
            utc=True,
        )

        print(f"Earliest: {timestamps.min()}")
        print(f"Latest:   {timestamps.max()}")
        print(f"Invalid:  {timestamps.isna().sum():,}")

    numeric_columns = [
        "LAT",
        "LON",
        "SOG",
        "COG",
        "Heading",
        "Length",
        "Width",
        "Draft",
    ]

    available_numeric_columns = [
        column for column in numeric_columns if column in dataframe.columns
    ]

    if available_numeric_columns:
        print("\n=== NUMERIC STATISTICS ===")

        numeric_data = dataframe[available_numeric_columns].apply(
            pd.to_numeric,
            errors="coerce",
        )

        print(
            numeric_data.describe()
            .transpose()
            .to_string(float_format=lambda value: f"{value:.3f}")
        )

    print("\n=== BASIC VALIDATION ===")

    if "LAT" in dataframe.columns:
        latitude = pd.to_numeric(
            dataframe["LAT"],
            errors="coerce",
        )

        invalid_latitude = (~latitude.between(-90, 90)).sum()

        print(f"Latitude outside -90 to 90: {invalid_latitude:,}")

    if "LON" in dataframe.columns:
        longitude = pd.to_numeric(
            dataframe["LON"],
            errors="coerce",
        )

        invalid_longitude = (~longitude.between(-180, 180)).sum()

        print(f"Longitude outside -180 to 180: {invalid_longitude:,}")

    if "SOG" in dataframe.columns:
        speed = pd.to_numeric(
            dataframe["SOG"],
            errors="coerce",
        )

        print(f"Unavailable SOG values (102.3): {(speed == 102.3).sum():,}")

        print(f"Negative SOG values: {(speed < 0).sum():,}")

    if "COG" in dataframe.columns:
        course = pd.to_numeric(
            dataframe["COG"],
            errors="coerce",
        )

        print(f"Unavailable COG values (360): {(course == 360).sum():,}")

    print("\nInspection complete.")


def main() -> None:
    """Run the AIS inspection script."""

    arguments = parse_arguments()

    inspect_ais_file(
        file_path=arguments.file,
        row_limit=arguments.rows,
    )


if __name__ == "__main__":
    main()
