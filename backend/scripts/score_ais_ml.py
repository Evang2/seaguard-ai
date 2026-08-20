from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from seaguard.ml.anomaly_detector import AISIsolationForestDetector
from seaguard.ml.feature_engineering import build_ais_features


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build AIS motion features and score them "
            "with the SeaGuard Isolation Forest detector."
        ),
    )

    parser.add_argument(
        "input_csv",
        type=Path,
        help="Path to the cleaned AIS CSV file.",
    )

    parser.add_argument(
        "output_csv",
        type=Path,
        help="Path where the ML-scored CSV will be written.",
    )

    parser.add_argument(
        "--contamination",
        type=float,
        default=None,
        help=(
            "Expected anomaly proportion, for example 0.01. "
            "If omitted, Isolation Forest uses 'auto'."
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    if not arguments.input_csv.exists():
        raise FileNotFoundError(
            f"Input CSV does not exist: {arguments.input_csv}",
        )

    print(f"Loading AIS data from {arguments.input_csv}...")

    dataframe = pd.read_csv(
        arguments.input_csv,
    )

    print(f"Loaded {len(dataframe):,} AIS observations.")

    print("Building ML features...")

    featured = build_ais_features(
        dataframe,
    )

    detector_kwargs: dict[str, object] = {}

    if arguments.contamination is not None:
        detector_kwargs["contamination"] = arguments.contamination

    detector = AISIsolationForestDetector(
        **detector_kwargs,
    )

    print("Training Isolation Forest...")

    scored = detector.fit_score(
        featured,
    )

    anomaly_count = int(
        scored["ml_is_anomaly"].sum(),
    )

    anomaly_percentage = 100.0 * anomaly_count / len(scored) if len(scored) > 0 else 0.0

    arguments.output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    scored.to_csv(
        arguments.output_csv,
        index=False,
    )

    print()
    print("ML scoring complete.")
    print(f"Observations: {len(scored):,}")
    print(f"ML anomalies: {anomaly_count:,}")
    print(f"Anomaly rate: {anomaly_percentage:.2f}%")
    print(f"Output: {arguments.output_csv}")

    print()
    print("Top 10 most anomalous observations:")

    columns = [
        column
        for column in [
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
            "sog",
            "reporting_gap_minutes",
            "calculated_speed_knots",
            "speed_difference_knots",
            "course_change_degrees",
            "ml_anomaly_score",
            "ml_is_anomaly",
        ]
        if column in scored.columns
    ]

    most_anomalous = scored.sort_values(
        "ml_anomaly_score",
        ascending=False,
    ).head(10)

    print(
        most_anomalous[columns].to_string(
            index=False,
        ),
    )


if __name__ == "__main__":
    main()
