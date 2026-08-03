import argparse
from pathlib import Path

import pandas as pd

from seaguard.visualization.trajectory_map import (
    create_trajectory_map,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "processed" / "maps"


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Create an interactive HTML map from an "
            "anomaly-annotated vessel trajectory."
        )
    )

    parser.add_argument(
        "file",
        type=Path,
        help=("Path to an anomaly-annotated trajectory CSV."),
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory for generated HTML maps.",
    )

    parser.add_argument(
        "--maximum-normal-markers",
        type=int,
        default=500,
        help=("Maximum number of normal observations displayed as markers."),
    )

    return parser.parse_args()


def main() -> None:
    """Create and save the interactive trajectory map."""

    arguments = parse_arguments()

    source_file = arguments.file.resolve()

    if not source_file.exists():
        raise FileNotFoundError(f"Annotated trajectory does not exist: {source_file}")

    if arguments.maximum_normal_markers < 0:
        raise ValueError("--maximum-normal-markers cannot be negative.")

    print(f"Reading: {source_file}")

    dataframe = pd.read_csv(
        source_file,
        low_memory=False,
        dtype={"mmsi": "string"},
    )

    if "mmsi" not in dataframe.columns:
        raise ValueError("The source file does not contain an MMSI column.")

    vessel_values = dataframe["mmsi"].dropna().astype("string").unique()

    if len(vessel_values) != 1:
        raise ValueError(
            "The annotated file must contain exactly one "
            f"MMSI. Found {len(vessel_values)}."
        )

    vessel_mmsi = str(vessel_values[0])

    output_directory = arguments.output_directory.resolve()

    output_file = output_directory / f"{vessel_mmsi}_trajectory_map.html"

    result = create_trajectory_map(
        dataframe,
        output_file,
        maximum_normal_markers=(arguments.maximum_normal_markers),
    )

    anomaly_count = 0

    if "has_anomaly" in dataframe.columns:
        anomaly_values = (
            dataframe["has_anomaly"]
            .astype("string")
            .str.lower()
            .isin({"true", "1", "yes"})
        )

        anomaly_count = int(anomaly_values.sum())

    print()
    print("Map created successfully.")
    print(f"MMSI:                 {vessel_mmsi}")
    print(f"Observations:         {len(dataframe):,}")
    print(f"Anomalous positions:  {anomaly_count:,}")
    print(f"Output:               {result}")
    print()
    print("Open the HTML file in a web browser to explore the trajectory.")


if __name__ == "__main__":
    main()
