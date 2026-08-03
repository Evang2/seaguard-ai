import argparse
from pathlib import Path

import pandas as pd

from seaguard.ais.trajectory import (
    build_trajectory_metrics,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "processed" / "trajectories"


def parse_arguments() -> argparse.Namespace:
    """Read command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct movement metrics for one vessel from a cleaned AIS CSV."
        )
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to a cleaned SeaGuard AIS CSV.",
    )

    parser.add_argument(
        "--mmsi",
        type=str,
        default=None,
        help=(
            "MMSI to analyse. When omitted, the vessel "
            "with the most observations is selected."
        ),
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=500_000,
        help="Maximum number of cleaned rows to read.",
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory for trajectory output.",
    )

    return parser.parse_args()


def main() -> None:
    """Analyse one vessel trajectory."""

    arguments = parse_arguments()

    source_file = arguments.file.resolve()

    if not source_file.exists():
        raise FileNotFoundError(f"Cleaned AIS file does not exist: {source_file}")

    print(f"Reading: {source_file}")
    print(f"Maximum rows: {arguments.rows:,}")

    source = pd.read_csv(
        source_file,
        nrows=arguments.rows,
        low_memory=False,
        dtype={"mmsi": "string"},
    )

    if "mmsi" not in source.columns:
        raise ValueError("The cleaned input file does not contain an 'mmsi' column.")

    selected_mmsi = arguments.mmsi

    if selected_mmsi is None:
        vessel_counts = source["mmsi"].value_counts(dropna=True)

        if vessel_counts.empty:
            raise ValueError("The input file contains no usable MMSI values.")

        selected_mmsi = str(vessel_counts.index[0])

        print("No MMSI supplied. Selecting the vessel with the most observations.")

    trajectory = build_trajectory_metrics(
        source=source,
        mmsi=selected_mmsi,
    )

    output_directory = arguments.output_directory.resolve()

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = output_directory / f"{selected_mmsi}_trajectory_metrics.csv"

    trajectory.to_csv(
        output_file,
        index=False,
    )

    observations = len(trajectory)
    start_time = trajectory["timestamp"].min()
    end_time = trajectory["timestamp"].max()

    total_distance = trajectory["distance_nm"].sum()

    maximum_gap = trajectory["reporting_gap_minutes"].max()

    maximum_calculated_speed = trajectory["calculated_speed_knots"].max()

    print()
    print("Trajectory complete.")
    print(f"MMSI:                    {selected_mmsi}")
    print(f"Observations:            {observations:,}")
    print(f"Start time:              {start_time}")
    print(f"End time:                {end_time}")
    print(f"Total calculated distance: {total_distance:.2f} nautical miles")
    print(f"Maximum reporting gap:     {maximum_gap:.2f} minutes")
    print(f"Maximum calculated speed:  {maximum_calculated_speed:.2f} knots")

    if "sog" in trajectory.columns:
        average_sog = trajectory["sog"].mean()

        print(f"Average reported SOG:       {average_sog:.2f} knots")

    if "course_change_degrees" in trajectory.columns:
        maximum_course_change = trajectory["course_change_degrees"].max()

        print(f"Maximum course change:      {maximum_course_change:.2f} degrees")

    print()
    print(f"Output: {output_file}")


if __name__ == "__main__":
    main()
