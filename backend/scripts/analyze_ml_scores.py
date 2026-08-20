from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze SeaGuard ML anomaly-score thresholds "
            "and rule-based anomaly context."
        ),
    )

    parser.add_argument(
        "input_csv",
        type=Path,
        help="ML/rule comparison CSV.",
    )

    return parser.parse_args()


def percentage(
    count: int,
    total: int,
) -> float:
    if total == 0:
        return 0.0

    return 100.0 * count / total


def analyze_score_threshold(
    dataframe: pd.DataFrame,
    top_percentage: float,
) -> None:
    score = dataframe["ml_anomaly_score"]

    threshold = score.quantile(
        1.0 - top_percentage / 100.0,
    )

    selected = dataframe[score >= threshold]

    rule_overlap = selected["rule_is_anomaly"].sum()

    print(
        f"Top {top_percentage:>4.1f}%"
        f" | threshold >= {threshold:>8.5f}"
        f" | rows {len(selected):>5,}"
        f" | rule overlap "
        f"{percentage(int(rule_overlap), len(selected)):>6.2f}%"
    )


def main() -> None:
    arguments = parse_arguments()

    if not arguments.input_csv.exists():
        raise FileNotFoundError(
            f"Input CSV does not exist: {arguments.input_csv}",
        )

    dataframe = pd.read_csv(
        arguments.input_csv,
    )

    required_columns = {
        "ml_anomaly_score",
        "ml_is_anomaly",
        "rule_is_anomaly",
        "sog",
        "reporting_gap_minutes",
        "course_change_degrees",
    }

    missing = required_columns.difference(
        dataframe.columns,
    )

    if missing:
        raise ValueError(
            "Missing required columns: " + ", ".join(sorted(missing)),
        )

    dataframe["ml_is_anomaly"] = (
        dataframe["ml_is_anomaly"].astype(str).str.lower().eq("true")
    )

    dataframe["rule_is_anomaly"] = (
        dataframe["rule_is_anomaly"].astype(str).str.lower().eq("true")
    )

    print()
    print("SeaGuard ML Score Analysis")
    print("==========================")

    print(f"Observations: {len(dataframe):,}")

    print()
    print("ML anomaly score distribution")
    print("-----------------------------")

    print(
        dataframe["ml_anomaly_score"]
        .describe(
            percentiles=[
                0.50,
                0.75,
                0.90,
                0.95,
                0.98,
                0.99,
                0.995,
            ],
        )
        .to_string()
    )

    print()
    print("Rank-based investigation thresholds")
    print("-----------------------------------")

    for top_percentage in [
        10.0,
        5.0,
        2.0,
        1.0,
        0.5,
    ]:
        analyze_score_threshold(
            dataframe,
            top_percentage,
        )

    long_gap = dataframe["reporting_gap_minutes"] > 15.0

    stationary = dataframe["sog"] < 3.0

    large_course_change = dataframe["course_change_degrees"] > 90.0

    ml_anomalies = dataframe["ml_is_anomaly"]

    rule_anomalies = dataframe["rule_is_anomaly"]

    rule_only = rule_anomalies & ~ml_anomalies

    print()
    print("Context diagnostics")
    print("-------------------")

    print(f"ML anomalies with >15 min gap: {int((ml_anomalies & long_gap).sum()):,}")

    print(
        f"Rule anomalies with >15 min gap: {int((rule_anomalies & long_gap).sum()):,}"
    )

    print(
        f"Rule-only anomalies while SOG < 3 kn: {int((rule_only & stationary).sum()):,}"
    )

    print(
        "Rule-only large course changes "
        "while SOG < 3 kn: "
        f"{int((rule_only & stationary & large_course_change).sum()):,}"
    )

    print()
    print("Highest scoring observations")
    print("----------------------------")

    columns = [
        column
        for column in [
            "mmsi",
            "timestamp",
            "sog",
            "reporting_gap_minutes",
            "calculated_speed_knots",
            "speed_difference_knots",
            "course_change_degrees",
            "heading_change_degrees",
            "absolute_acceleration_knots_per_minute",
            "rule_flag_count",
            "ml_anomaly_score",
            "ml_is_anomaly",
            "rule_is_anomaly",
        ]
        if column in dataframe.columns
    ]

    print(
        dataframe.sort_values(
            "ml_anomaly_score",
            ascending=False,
        )[columns]
        .head(20)
        .to_string(
            index=False,
        )
    )


if __name__ == "__main__":
    main()
