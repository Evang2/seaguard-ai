from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from seaguard.ais.anomalies import detect_rule_based_anomalies
from seaguard.risk.hybrid import HybridRiskAssessor

RISK_ORDER = [
    "low",
    "medium",
    "high",
    "critical",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply SeaGuard's production rule detector and "
            "hybrid ML/rule risk classifier to an ML-scored AIS CSV."
        ),
    )

    parser.add_argument(
        "input_csv",
        type=Path,
        help=("Input CSV containing engineered AIS fields and ml_anomaly_score."),
    )

    parser.add_argument(
        "output_csv",
        type=Path,
        help="Output CSV containing hybrid risk fields.",
    )

    return parser.parse_args()


def percentage(
    count: int,
    total: int,
) -> float:
    if total == 0:
        return 0.0

    return 100.0 * count / total


def print_distribution(
    dataframe: pd.DataFrame,
) -> None:
    total = len(dataframe)

    print()
    print("Hybrid risk distribution")
    print("========================")

    for level in RISK_ORDER:
        count = int(dataframe["risk_level"].eq(level).sum())

        print(f"{level.upper():<10}{count:>6,} ({percentage(count, total):>6.2f}%)")


def print_rule_severity_distribution(
    dataframe: pd.DataFrame,
) -> None:
    print()
    print("Rule severity distribution")
    print("==========================")

    for severity in [
        "none",
        "warning",
        "high",
        "critical",
    ]:
        count = int(dataframe["rule_severity"].eq(severity).sum())

        print(f"{severity.upper():<10}{count:>6,}")


def print_top_risk_observations(
    dataframe: pd.DataFrame,
    *,
    limit: int = 20,
) -> None:
    print()
    print("Highest-priority observations")
    print("=============================")

    risk_rank = {
        "low": 0,
        "medium": 1,
        "high": 2,
        "critical": 3,
    }

    ranked = dataframe.copy()

    ranked["_risk_rank"] = ranked["risk_level"].map(risk_rank).fillna(-1)

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
            "heading_change_degrees",
            "absolute_acceleration_knots_per_minute",
            "ml_anomaly_score",
            "ml_anomaly_percentile",
            "rule_flag_count",
            "rule_severity",
            "detector_agreement",
            "risk_level",
            "risk_reasons",
        ]
        if column in ranked.columns
    ]

    selected = ranked.sort_values(
        [
            "_risk_rank",
            "ml_anomaly_percentile",
            "rule_flag_count",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    ).head(limit)

    print(
        selected[columns].to_string(
            index=False,
        )
    )


def main() -> None:
    arguments = parse_arguments()

    if not arguments.input_csv.exists():
        raise FileNotFoundError(
            f"Input CSV does not exist: {arguments.input_csv}",
        )

    print(f"Loading ML-scored AIS data from {arguments.input_csv}...")

    dataframe = pd.read_csv(
        arguments.input_csv,
    )

    if "ml_anomaly_score" not in dataframe.columns:
        raise ValueError(
            "Input CSV does not contain ml_anomaly_score. Run score_ais_ml.py first.",
        )

    print(f"Loaded {len(dataframe):,} AIS observations.")

    print("Applying production rule-based detector...")

    annotated, _ = detect_rule_based_anomalies(
        dataframe,
    )

    print("Calibrating ML score percentiles...")

    assessor = HybridRiskAssessor()

    assessor.fit(
        annotated,
    )

    print("Assessing hybrid risk...")

    assessed = assessor.assess(
        annotated,
    )

    total = len(assessed)

    rule_anomalies = int(assessed["rule_flag_count"].gt(0).sum())

    detector_agreement = int(assessed["detector_agreement"].sum())

    ml_top_5_percent = int(assessed["ml_anomaly_percentile"].ge(95.0).sum())

    print()
    print("SeaGuard Hybrid Risk Assessment")
    print("===============================")
    print(f"Observations:        {total:,}")

    print(
        "Rule anomalies:      "
        f"{rule_anomalies:,} "
        f"({percentage(rule_anomalies, total):.2f}%)"
    )

    print(
        "ML >= 95th pct:      "
        f"{ml_top_5_percent:,} "
        f"({percentage(ml_top_5_percent, total):.2f}%)"
    )

    print(
        "Detector agreement:  "
        f"{detector_agreement:,} "
        f"({percentage(detector_agreement, total):.2f}%)"
    )

    print_distribution(
        assessed,
    )

    print_rule_severity_distribution(
        assessed,
    )

    print_top_risk_observations(
        assessed,
    )

    arguments.output_csv.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    assessed.to_csv(
        arguments.output_csv,
        index=False,
    )

    print()
    print(f"Hybrid risk CSV written to: {arguments.output_csv}")


if __name__ == "__main__":
    main()
