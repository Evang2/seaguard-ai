import pandas as pd

from seaguard.ais.anomalies import (
    AnomalyThresholds,
    detect_rule_based_anomalies,
)


def test_detect_rule_based_anomalies() -> None:
    """A valid short interval should trigger explainable motion alerts."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:00:00Z",
                "reporting_gap_minutes": None,
                "elapsed_seconds": None,
                "calculated_speed_knots": None,
                "speed_difference_knots": None,
                "course_change_degrees": None,
                "heading_change_degrees": None,
                "acceleration_knots_per_minute": None,
                "sog": 10.0,
                "nonpositive_time_interval": False,
            },
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:05:00Z",
                "reporting_gap_minutes": 5.0,
                "elapsed_seconds": 300.0,
                "calculated_speed_knots": 80.0,
                "speed_difference_knots": 25.0,
                "course_change_degrees": 120.0,
                "heading_change_degrees": 110.0,
                "acceleration_knots_per_minute": 9.0,
                "sog": 12.0,
                "nonpositive_time_interval": False,
            },
        ]
    )

    annotated, alerts = detect_rule_based_anomalies(source)

    anomalous_row = annotated.iloc[1]

    assert not bool(anomalous_row["flag_reporting_gap"])

    assert bool(anomalous_row["flag_position_jump"])
    assert bool(anomalous_row["flag_speed_mismatch"])
    assert bool(anomalous_row["flag_rapid_course_change"])
    assert bool(anomalous_row["flag_rapid_heading_change"])
    assert bool(anomalous_row["flag_extreme_acceleration"])

    assert anomalous_row["anomaly_count"] == 5
    assert len(alerts) == 5

    anomaly_types = set(alerts["anomaly_type"])

    assert "position_jump" in anomaly_types
    assert "speed_mismatch" in anomaly_types
    assert "rapid_course_change" in anomaly_types
    assert "rapid_heading_change" in anomaly_types
    assert "extreme_acceleration" in anomaly_types


def test_long_reporting_gap_does_not_create_motion_anomalies() -> None:
    """A long gap should not create derived motion anomalies."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:00:00Z",
                "reporting_gap_minutes": None,
                "elapsed_seconds": None,
                "calculated_speed_knots": None,
                "speed_difference_knots": None,
                "course_change_degrees": None,
                "heading_change_degrees": None,
                "acceleration_knots_per_minute": None,
                "sog": 10.0,
                "nonpositive_time_interval": False,
            },
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:20:00Z",
                "reporting_gap_minutes": 20.0,
                "elapsed_seconds": 1200.0,
                "calculated_speed_knots": 100.0,
                "speed_difference_knots": 50.0,
                "course_change_degrees": 170.0,
                "heading_change_degrees": 170.0,
                "acceleration_knots_per_minute": 20.0,
                "sog": 20.0,
                "nonpositive_time_interval": False,
            },
        ]
    )

    annotated, alerts = detect_rule_based_anomalies(source)

    anomalous_row = annotated.iloc[1]

    assert bool(anomalous_row["flag_reporting_gap"])

    assert not bool(anomalous_row["flag_position_jump"])
    assert not bool(anomalous_row["flag_speed_mismatch"])
    assert not bool(anomalous_row["flag_rapid_course_change"])
    assert not bool(anomalous_row["flag_rapid_heading_change"])
    assert not bool(anomalous_row["flag_extreme_acceleration"])

    assert anomalous_row["anomaly_count"] == 1
    assert len(alerts) == 1
    assert alerts.iloc[0]["anomaly_type"] == "reporting_gap"


def test_rapid_turn_requires_moving_vessel() -> None:
    """Low-speed directional changes should not trigger turn alerts."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:05:00Z",
                "reporting_gap_minutes": 5.0,
                "elapsed_seconds": 300.0,
                "course_change_degrees": 150.0,
                "heading_change_degrees": 160.0,
                "sog": 0.5,
            }
        ]
    )

    annotated, alerts = detect_rule_based_anomalies(source)

    assert not bool(annotated.iloc[0]["flag_rapid_course_change"])

    assert not bool(annotated.iloc[0]["flag_rapid_heading_change"])

    assert alerts.empty


def test_custom_thresholds() -> None:
    """Thresholds should be configurable."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2024-06-15T00:05:00Z",
                "reporting_gap_minutes": 6.0,
                "elapsed_seconds": 360.0,
                "calculated_speed_knots": 30.0,
                "sog": 10.0,
            }
        ]
    )

    thresholds = AnomalyThresholds(
        reporting_gap_minutes=5.0,
        position_jump_speed_knots=25.0,
    )

    annotated, alerts = detect_rule_based_anomalies(
        source,
        thresholds=thresholds,
    )

    assert bool(annotated.iloc[0]["flag_reporting_gap"])

    assert bool(annotated.iloc[0]["flag_position_jump"])

    assert len(alerts) == 2


def test_alert_contains_message_identity() -> None:
    """Alerts should contain the position needed for DB matching."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2026-07-01T10:00:00Z",
                "latitude": 37.9838,
                "longitude": 23.7275,
                "reporting_gap_minutes": 20.0,
                "elapsed_seconds": 1200.0,
                "sog": 10.0,
            }
        ]
    )

    _, alerts = detect_rule_based_anomalies(source)

    assert len(alerts) == 1
    assert alerts.iloc[0]["mmsi"] == "123456789"
    assert alerts.iloc[0]["latitude"] == 37.9838
    assert alerts.iloc[0]["longitude"] == 23.7275
    assert alerts.iloc[0]["anomaly_type"] == "reporting_gap"
