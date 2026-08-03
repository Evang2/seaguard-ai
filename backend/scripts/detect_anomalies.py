import argparse
import json
from pathlib import Path

import pandas as pd

from seaguard.ais.anomalies import (
    AnomalyThresholds,
    detect_rule_based_anomalies,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "processed" / "anomalies"


def parse_arguments() -> argparse.Namespace:
    """Read anomaly-detection command-line options."""

    parser = argparse.ArgumentParser(
        description=(
            "Apply explainable rule-based anomaly detection "
            "to a SeaGuard trajectory CSV."
        )
    )

    parser.add_argument(
        "file",
        type=Path,
        help="Path to a trajectory-metrics CSV.",
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory for anomaly output files.",
    )

    parser.add_argument(
        "--reporting-gap",
        type=float,
        default=15.0,
        help="Reporting-gap threshold in minutes.",
    )

    parser.add_argument(
        "--position-jump-speed",
        type=float,
        default=60.0,
        help="Calculated-speed threshold in knots.",
    )

    parser.add_argument(
        "--speed-difference",
        type=float,
        default=15.0,
        help="Reported/calculated speed difference in knots.",
    )

    return parser.parse_args()


def main() -> None:
    """Run rule-based anomaly detection."""

    arguments = parse_arguments()

    source_file = arguments.file.resolve()

    if not source_file.exists():
        raise FileNotFoundError(f"Trajectory file does not exist: {source_file}")

    output_directory = arguments.output_directory.resolve()

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Reading: {source_file}")

    trajectory = pd.read_csv(
        source_file,
        low_memory=False,
        dtype={"mmsi": "string"},
    )

    thresholds = AnomalyThresholds(
        reporting_gap_minutes=arguments.reporting_gap,
        position_jump_speed_knots=(arguments.position_jump_speed),
        speed_difference_knots=(arguments.speed_difference),
    )

    annotated, alerts = detect_rule_based_anomalies(
        trajectory,
        thresholds=thresholds,
    )

    source_stem = source_file.stem

    annotated_file = output_directory / f"{source_stem}_annotated.csv"

    alerts_file = output_directory / f"{source_stem}_alerts.csv"

    summary_file = output_directory / f"{source_stem}_summary.json"

    annotated.to_csv(
        annotated_file,
        index=False,
    )

    alerts.to_csv(
        alerts_file,
        index=False,
    )

    anomaly_counts = (
        alerts["anomaly_type"].value_counts().to_dict() if not alerts.empty else {}
    )

    severity_counts = (
        alerts["severity"].value_counts().to_dict() if not alerts.empty else {}
    )

    summary = {
        "source_file": str(source_file),
        "observations": int(len(annotated)),
        "anomalous_observations": int(annotated["has_anomaly"].sum()),
        "total_alerts": int(len(alerts)),
        "anomaly_counts": {
            str(key): int(value) for key, value in anomaly_counts.items()
        },
        "severity_counts": {
            str(key): int(value) for key, value in severity_counts.items()
        },
        "thresholds": {
            "reporting_gap_minutes": (thresholds.reporting_gap_minutes),
            "position_jump_speed_knots": (thresholds.position_jump_speed_knots),
            "speed_difference_knots": (thresholds.speed_difference_knots),
            "course_change_degrees": (thresholds.course_change_degrees),
            "heading_change_degrees": (thresholds.heading_change_degrees),
            "acceleration_knots_per_minute": (thresholds.acceleration_knots_per_minute),
        },
    }

    with summary_file.open(
        mode="w",
        encoding="utf-8",
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
        )

    print()
    print("Detection complete.")
    print(f"Observations:          {len(annotated):,}")
    print(f"Anomalous observations: {annotated['has_anomaly'].sum():,}")
    print(f"Total alerts:          {len(alerts):,}")

    if anomaly_counts:
        print()
        print("Alerts by type:")

        for anomaly_type, count in anomaly_counts.items():
            print(f"  {anomaly_type}: {count:,}")

    print()
    print(f"Annotated data: {annotated_file}")
    print(f"Alerts:         {alerts_file}")
    print(f"Summary:        {summary_file}")


if __name__ == "__main__":
    main()
