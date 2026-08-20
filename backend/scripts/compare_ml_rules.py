from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

REPORTING_GAP_MINUTES = 15.0
POSITION_JUMP_SPEED_KNOTS = 60.0
SPEED_DIFFERENCE_KNOTS = 15.0
COURSE_CHANGE_DEGREES = 90.0
HEADING_CHANGE_DEGREES = 90.0
MAXIMUM_TURN_INTERVAL_MINUTES = 10.0
MINIMUM_TURN_SPEED_KNOTS = 3.0
ACCELERATION_KNOTS_PER_MINUTE = 8.0


RULE_COLUMNS = [
    "rule_reporting_gap",
    "rule_position_jump",
    "rule_speed_mismatch",
    "rule_rapid_course_change",
    "rule_rapid_heading_change",
    "rule_high_acceleration",
    "rule_nonpositive_interval",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare SeaGuard Isolation Forest anomalies "
            "against rule-based AIS anomaly signals."
        ),
    )

    parser.add_argument(
        "input_csv",
        type=Path,
        help="ML-scored AIS CSV.",
    )

    parser.add_argument(
        "output_csv",
        type=Path,
        help="Output CSV containing ML and rule comparison fields.",
    )

    return parser.parse_args()


def numeric(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(
            np.nan,
            index=dataframe.index,
            dtype=float,
        )

    return pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )


def boolean_ml_predictions(
    series: pd.Series,
) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(
            {
                "true",
                "1",
                "yes",
            },
        )
    )


def add_rule_flags(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    result = dataframe.copy()

    reporting_gap = numeric(
        result,
        "reporting_gap_minutes",
    )

    calculated_speed = numeric(
        result,
        "calculated_speed_knots",
    )

    speed_difference = numeric(
        result,
        "speed_difference_knots",
    )

    course_change = numeric(
        result,
        "course_change_degrees",
    )

    heading_change = numeric(
        result,
        "heading_change_degrees",
    )

    acceleration = numeric(
        result,
        "absolute_acceleration_knots_per_minute",
    )

    elapsed_seconds = numeric(
        result,
        "elapsed_seconds",
    )

    sog = numeric(
        result,
        "sog",
    )

    valid_motion_interval = (
        reporting_gap.notna()
        & (reporting_gap > 0.0)
        & (reporting_gap <= MAXIMUM_TURN_INTERVAL_MINUTES)
    )

    valid_turn_context = (
        valid_motion_interval & sog.notna() & (sog >= MINIMUM_TURN_SPEED_KNOTS)
    )

    result["rule_reporting_gap"] = reporting_gap > REPORTING_GAP_MINUTES

    result["rule_position_jump"] = valid_motion_interval & (
        calculated_speed > POSITION_JUMP_SPEED_KNOTS
    )

    result["rule_speed_mismatch"] = valid_motion_interval & (
        speed_difference > SPEED_DIFFERENCE_KNOTS
    )

    result["rule_rapid_course_change"] = valid_turn_context & (
        course_change > COURSE_CHANGE_DEGREES
    )

    result["rule_rapid_heading_change"] = valid_turn_context & (
        heading_change > HEADING_CHANGE_DEGREES
    )

    result["rule_high_acceleration"] = valid_motion_interval & (
        acceleration > ACCELERATION_KNOTS_PER_MINUTE
    )

    result["rule_nonpositive_interval"] = elapsed_seconds.notna() & (
        elapsed_seconds <= 0.0
    )

    result["rule_flag_count"] = result[RULE_COLUMNS].sum(axis=1).astype(int)

    result["rule_is_anomaly"] = result["rule_flag_count"] > 0

    return result


def print_examples(
    dataframe: pd.DataFrame,
    title: str,
    *,
    limit: int = 10,
) -> None:
    print()
    print(title)
    print("-" * len(title))

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

    if dataframe.empty:
        print("None")
        return

    print(
        dataframe.sort_values(
            "ml_anomaly_score",
            ascending=False,
        )[columns]
        .head(limit)
        .to_string(
            index=False,
        ),
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

    if "ml_is_anomaly" not in dataframe.columns:
        raise ValueError(
            "Input CSV does not contain ml_is_anomaly. Run score_ais_ml.py first.",
        )

    if "ml_anomaly_score" not in dataframe.columns:
        raise ValueError(
            "Input CSV does not contain ml_anomaly_score.",
        )

    dataframe["ml_is_anomaly"] = boolean_ml_predictions(
        dataframe["ml_is_anomaly"],
    )

    result = add_rule_flags(
        dataframe,
    )

    both = result["ml_is_anomaly"] & result["rule_is_anomaly"]

    ml_only = result["ml_is_anomaly"] & ~result["rule_is_anomaly"]

    rules_only = ~result["ml_is_anomaly"] & result["rule_is_anomaly"]

    neither = ~result["ml_is_anomaly"] & ~result["rule_is_anomaly"]

    total = len(result)

    print()
    print("SeaGuard ML vs Rule Comparison")
    print("==============================")
    print(f"Observations:       {total:,}")

    print(f"ML anomalies:       {int(result['ml_is_anomaly'].sum()):,}")

    print(f"Rule anomalies:     {int(result['rule_is_anomaly'].sum()):,}")

    print()
    print(f"Both ML + rules:    {int(both.sum()):,}")
    print(f"ML only:            {int(ml_only.sum()):,}")
    print(f"Rules only:         {int(rules_only.sum()):,}")
    print(f"Neither:            {int(neither.sum()):,}")

    if result["ml_is_anomaly"].any():
        overlap = both.sum() / result["ml_is_anomaly"].sum() * 100.0

        print()
        print(f"ML anomalies also caught by rules: {overlap:.2f}%")

    print()
    print("Individual rule counts")
    print("----------------------")

    for column in RULE_COLUMNS:
        print(f"{column:<32}{int(result[column].sum()):>8,}")

    print_examples(
        result.loc[both],
        "Top anomalies detected by BOTH ML and rules",
    )

    print_examples(
        result.loc[ml_only],
        "Top ML-ONLY anomalies",
    )

    print_examples(
        result.loc[rules_only],
        "Top RULE-ONLY anomalies",
    )

    arguments.output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        arguments.output_csv,
        index=False,
    )

    print()
    print(f"Comparison CSV written to: {arguments.output_csv}")


if __name__ == "__main__":
    main()
