import pandas as pd

from seaguard.db.anomaly_importer import (
    _build_alert_records,
    _identity_key,
    _prepare_alert_chunk,
)


def test_prepare_alert_chunk_rejects_invalid_rows() -> None:
    """Invalid alert identities should be rejected."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": "2026-07-01T10:00:00Z",
                "latitude": 37.9838,
                "longitude": 23.7275,
                "anomaly_type": "reporting_gap",
                "severity": "warning",
                "metric_name": ("reporting_gap_minutes"),
                "metric_value": 20.0,
                "threshold": 15.0,
                "message": "Reporting gap detected.",
            },
            {
                "mmsi": "invalid",
                "timestamp": "not-a-date",
                "latitude": 100.0,
                "longitude": 23.7275,
                "anomaly_type": "",
                "severity": "warning",
                "metric_name": "test",
                "message": "Invalid alert.",
            },
        ]
    )

    prepared, rejected_count = _prepare_alert_chunk(source)

    assert len(prepared) == 1
    assert rejected_count == 1


def test_build_alert_records_links_message() -> None:
    """An alert should link to its exact AIS message."""

    timestamp = pd.Timestamp("2026-07-01T10:00:00Z")

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": timestamp,
                "latitude": 37.9838,
                "longitude": 23.7275,
                "anomaly_type": "position_jump",
                "severity": "critical",
                "metric_name": ("calculated_speed_knots"),
                "metric_value": 80.0,
                "threshold": 60.0,
                "message": "Position jump detected.",
            }
        ]
    )

    identity = _identity_key(
        "123456789",
        timestamp,
        37.9838,
        23.7275,
    )

    records, messages_not_found = _build_alert_records(
        source,
        message_links={
            identity: (42, 7),
        },
    )

    assert messages_not_found == 0
    assert len(records) == 1

    record = records[0]

    assert record["ais_message_id"] == 42
    assert record["vessel_id"] == 7
    assert record["anomaly_type"] == ("position_jump")


def test_build_alert_records_counts_missing_message() -> None:
    """Alerts without an imported AIS message should be skipped."""

    source = pd.DataFrame(
        [
            {
                "mmsi": "123456789",
                "timestamp": pd.Timestamp("2026-07-01T10:00:00Z"),
                "latitude": 37.9838,
                "longitude": 23.7275,
                "anomaly_type": "reporting_gap",
                "severity": "warning",
                "metric_name": ("reporting_gap_minutes"),
                "metric_value": 20.0,
                "threshold": 15.0,
                "message": "Reporting gap detected.",
            }
        ]
    )

    records, messages_not_found = _build_alert_records(
        source,
        message_links={},
    )

    assert records == []
    assert messages_not_found == 1
