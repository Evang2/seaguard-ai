from datetime import UTC, datetime

import pandas as pd
import pytest

from seaguard.db.risk_importer import (
    _build_risk_records,
    _prepare_risk_chunk,
)


def _valid_row() -> dict[str, object]:
    return {
        "mmsi": "367784640",
        "timestamp": "2024-06-14T13:05:28Z",
        "ml_anomaly_score": 0.253998,
        "ml_anomaly_percentile": 99.98,
        "rule_flag_count": 3,
        "rule_severity": "high",
        "detector_agreement": True,
        "risk_level": "critical",
        "risk_reasons": (
            "rules=speed_mismatch,"
            "rapid_course_change,"
            "rapid_heading_change; "
            "ml_percentile=99.98"
        ),
    }


def test_prepare_risk_chunk_normalizes_valid_rows() -> None:
    source = pd.DataFrame([_valid_row()])

    prepared, rejected = _prepare_risk_chunk(source)

    assert rejected == 0
    assert len(prepared) == 1

    row = prepared.iloc[0]

    assert row["mmsi"] == "367784640"
    assert str(row["timestamp"]) == "2024-06-14 13:05:28+00:00"
    assert row["rule_flag_count"] == 3
    assert bool(row["detector_agreement"])
    assert row["risk_level"] == "critical"


def test_prepare_risk_chunk_rejects_invalid_rows() -> None:
    valid = _valid_row()

    source = pd.DataFrame(
        [
            valid,
            {**valid, "mmsi": "123"},
            {
                **valid,
                "ml_anomaly_percentile": 101.0,
            },
            {
                **valid,
                "risk_level": "dangerous",
            },
        ]
    )

    prepared, rejected = _prepare_risk_chunk(source)

    assert len(prepared) == 1
    assert rejected == 3


def test_prepare_risk_chunk_requires_expected_columns() -> None:
    source = pd.DataFrame(
        [
            {
                "mmsi": "367784640",
                "timestamp": "2024-06-14T13:05:28Z",
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match="Missing required risk import columns",
    ):
        _prepare_risk_chunk(source)


def test_build_risk_records_links_existing_message() -> None:
    prepared, _ = _prepare_risk_chunk(pd.DataFrame([_valid_row()]))

    observed_at = datetime(
        2024,
        6,
        14,
        13,
        5,
        28,
        tzinfo=UTC,
    )

    vessel_ids = {"367784640": 12}
    message_ids = {(12, observed_at): 345}

    records, missing = _build_risk_records(
        prepared,
        vessel_ids,
        message_ids,
        assessment_version="hybrid-v1",
    )

    assert missing == 0
    assert len(records) == 1

    record = records[0]

    assert record["ais_message_id"] == 345
    assert record["vessel_id"] == 12
    assert record["risk_level"] == "critical"
    assert record["ml_anomaly_percentile"] == pytest.approx(99.98)
    assert record["assessment_version"] == "hybrid-v1"


def test_build_risk_records_counts_missing_message() -> None:
    prepared, _ = _prepare_risk_chunk(pd.DataFrame([_valid_row()]))

    records, missing = _build_risk_records(
        prepared,
        {"367784640": 12},
        {},
        assessment_version="hybrid-v1",
    )

    assert records == []
    assert missing == 1
