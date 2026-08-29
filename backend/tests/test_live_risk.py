from datetime import UTC, datetime, timedelta

import pandas as pd

from seaguard.ais.anomalies import detect_rule_based_anomalies
from seaguard.ingestion.live_anomalies import build_live_motion_features
from seaguard.ml.anomaly_detector import AISIsolationForestDetector
from seaguard.risk.hybrid import HybridRiskAssessor


def _reference_dataframe() -> pd.DataFrame:
    start = datetime(
        2024,
        6,
        14,
        12,
        0,
        tzinfo=UTC,
    )

    rows: list[dict[str, object]] = []

    for index in range(30):
        rows.append(
            {
                "id": index + 1,
                "mmsi": "111111111",
                "timestamp": (start + timedelta(minutes=index)),
                "latitude": (40.7000 + index * 0.0004),
                "longitude": (-74.0100 + index * 0.0003),
                "sog": (8.0 + (index % 4) * 0.2),
                "cog": (80.0 + index * 1.5) % 360.0,
                "heading": (80.0 + index * 1.5) % 360.0,
            }
        )

    return pd.DataFrame(rows)


def test_live_motion_features_include_ml_columns() -> None:
    features = build_live_motion_features(_reference_dataframe())

    assert {
        "sog",
        "reporting_gap_minutes",
        "distance_nm",
        "calculated_speed_knots",
        "speed_difference_knots",
        "course_change_degrees",
        "heading_change_degrees",
        "absolute_acceleration_knots_per_minute",
        "turn_rate_degrees_per_minute",
    }.issubset(features.columns)


def test_live_motion_features_calculate_absolute_acceleration() -> None:
    features = build_live_motion_features(_reference_dataframe())

    acceleration = features["acceleration_knots_per_minute"].dropna()

    absolute = features["absolute_acceleration_knots_per_minute"].dropna()

    assert len(acceleration) == len(absolute)

    assert (absolute >= 0.0).all()


def test_live_motion_features_calculate_turn_rate() -> None:
    features = build_live_motion_features(_reference_dataframe())

    valid = features["course_change_degrees"].notna() & features[
        "reporting_gap_minutes"
    ].gt(0.0)

    expected = (
        features.loc[
            valid,
            "course_change_degrees",
        ]
        / features.loc[
            valid,
            "reporting_gap_minutes",
        ]
    )

    actual = features.loc[
        valid,
        "turn_rate_degrees_per_minute",
    ]

    pd.testing.assert_series_equal(
        actual.reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
    )


def test_stable_detector_can_score_new_rows_without_refit() -> None:
    features = build_live_motion_features(_reference_dataframe())

    annotated, _ = detect_rule_based_anomalies(features)

    detector = AISIsolationForestDetector()

    detector.fit(annotated)

    scored_reference = detector.score(annotated)

    assessor = HybridRiskAssessor()

    assessor.fit(scored_reference)

    incoming = annotated.tail(2).copy()

    scored_incoming = detector.score(incoming)

    assessed = assessor.assess(scored_incoming)

    assert len(assessed) == 2

    assert {
        "ml_anomaly_score",
        "ml_anomaly_percentile",
        "rule_flag_count",
        "rule_severity",
        "detector_agreement",
        "risk_level",
        "risk_reasons",
    }.issubset(assessed.columns)

    assert (
        assessed["ml_anomaly_percentile"]
        .between(
            0.0,
            100.0,
        )
        .all()
    )
