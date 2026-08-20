import pandas as pd
import pytest

from seaguard.risk.hybrid import HybridRiskAssessor


def _reference_scores() -> pd.DataFrame:
    return pd.DataFrame({"ml_anomaly_score": [float(value) for value in range(1, 201)]})


def _base_row(
    *,
    ml_anomaly_score: float,
) -> dict[str, object]:
    return {
        "ml_anomaly_score": ml_anomaly_score,
        "flag_reporting_gap": False,
        "flag_position_jump": False,
        "flag_speed_mismatch": False,
        "flag_rapid_course_change": False,
        "flag_rapid_heading_change": False,
        "flag_extreme_acceleration": False,
        "flag_nonpositive_interval": False,
    }


def test_low_risk_when_no_elevated_evidence() -> None:
    assessor = HybridRiskAssessor().fit(
        _reference_scores(),
    )

    source = pd.DataFrame(
        [
            _base_row(
                ml_anomaly_score=20.0,
            )
        ]
    )

    result = assessor.assess(source)

    assert result.iloc[0]["risk_level"] == "low"
    assert result.iloc[0]["rule_flag_count"] == 0
    assert not bool(result.iloc[0]["detector_agreement"])


def test_warning_rule_produces_medium_risk() -> None:
    assessor = HybridRiskAssessor().fit(
        _reference_scores(),
    )

    row = _base_row(
        ml_anomaly_score=20.0,
    )

    row["flag_reporting_gap"] = True

    result = assessor.assess(
        pd.DataFrame([row]),
    )

    assert result.iloc[0]["risk_level"] == "medium"
    assert result.iloc[0]["rule_severity"] == "warning"


def test_high_rule_produces_high_risk() -> None:
    assessor = HybridRiskAssessor().fit(
        _reference_scores(),
    )

    row = _base_row(
        ml_anomaly_score=20.0,
    )

    row["flag_extreme_acceleration"] = True

    result = assessor.assess(
        pd.DataFrame([row]),
    )

    assert result.iloc[0]["risk_level"] == "high"
    assert result.iloc[0]["rule_severity"] == "high"


def test_critical_rule_produces_critical_risk() -> None:
    assessor = HybridRiskAssessor().fit(
        _reference_scores(),
    )

    row = _base_row(
        ml_anomaly_score=20.0,
    )

    row["flag_position_jump"] = True

    result = assessor.assess(
        pd.DataFrame([row]),
    )

    assert result.iloc[0]["risk_level"] == "critical"
    assert result.iloc[0]["rule_severity"] == "critical"


def test_extreme_ml_score_without_rule_is_high_risk() -> None:
    assessor = HybridRiskAssessor().fit(
        _reference_scores(),
    )

    source = pd.DataFrame(
        [
            _base_row(
                ml_anomaly_score=200.0,
            )
        ]
    )

    result = assessor.assess(source)

    assert result.iloc[0]["ml_anomaly_percentile"] == 100.0
    assert result.iloc[0]["risk_level"] == "high"


def test_very_high_ml_plus_multiple_rules_is_critical() -> None:
    assessor = HybridRiskAssessor().fit(
        _reference_scores(),
    )

    row = _base_row(
        ml_anomaly_score=199.0,
    )

    row["flag_reporting_gap"] = True
    row["flag_rapid_course_change"] = True

    result = assessor.assess(
        pd.DataFrame([row]),
    )

    assert result.iloc[0]["ml_anomaly_percentile"] >= 99.0

    assert result.iloc[0]["rule_flag_count"] == 2
    assert bool(result.iloc[0]["detector_agreement"])
    assert result.iloc[0]["risk_level"] == "critical"


def test_assessor_requires_fit_before_assessment() -> None:
    assessor = HybridRiskAssessor()

    source = pd.DataFrame(
        [
            _base_row(
                ml_anomaly_score=20.0,
            )
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="must be fitted",
    ):
        assessor.assess(source)


def test_missing_rule_column_raises_error() -> None:
    assessor = HybridRiskAssessor().fit(
        _reference_scores(),
    )

    source = pd.DataFrame(
        [
            {
                "ml_anomaly_score": 20.0,
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match="Missing required rule column",
    ):
        assessor.assess(source)
