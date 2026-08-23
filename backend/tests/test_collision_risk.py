import pytest

from seaguard.collision.geometry import (
    CPAResult,
)
from seaguard.collision.risk import (
    CollisionRiskThresholds,
    assess_collision_risk,
)


def make_cpa_result(
    *,
    current_distance_nm: float = 5.0,
    relative_speed_knots: float = 10.0,
    closing_speed_knots: float = 10.0,
    tcpa_minutes: float | None = 20.0,
    cpa_distance_nm: float = 0.5,
    future_cpa_distance_nm: float = 0.5,
    is_closing: bool = True,
) -> CPAResult:
    return CPAResult(
        current_distance_nm=current_distance_nm,
        relative_speed_knots=relative_speed_knots,
        closing_speed_knots=closing_speed_knots,
        bearing_from_a_to_b_degrees=90.0,
        tcpa_minutes=tcpa_minutes,
        cpa_distance_nm=cpa_distance_nm,
        future_cpa_distance_nm=(future_cpa_distance_nm),
        is_closing=is_closing,
    )


def test_critical_imminent_close_approach() -> None:
    result = make_cpa_result(
        current_distance_nm=3.0,
        tcpa_minutes=10.0,
        cpa_distance_nm=0.15,
        future_cpa_distance_nm=0.15,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "critical"

    assert assessment.cpa_distance_nm == pytest.approx(0.15)

    assert any("0.25 NM" in reason for reason in assessment.reasons)


def test_high_collision_risk() -> None:
    result = make_cpa_result(
        tcpa_minutes=22.0,
        cpa_distance_nm=0.40,
        future_cpa_distance_nm=0.40,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "high"


def test_medium_collision_risk() -> None:
    result = make_cpa_result(
        tcpa_minutes=40.0,
        cpa_distance_nm=0.80,
        future_cpa_distance_nm=0.80,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "medium"


def test_safe_projected_separation_is_low() -> None:
    result = make_cpa_result(
        tcpa_minutes=20.0,
        cpa_distance_nm=2.5,
        future_cpa_distance_nm=2.5,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "low"


def test_far_future_encounter_is_low() -> None:
    result = make_cpa_result(
        tcpa_minutes=90.0,
        cpa_distance_nm=0.10,
        future_cpa_distance_nm=0.10,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "low"


def test_diverging_encounter_is_low() -> None:
    result = make_cpa_result(
        current_distance_nm=3.0,
        closing_speed_knots=-10.0,
        tcpa_minutes=-12.0,
        cpa_distance_nm=0.1,
        future_cpa_distance_nm=3.0,
        is_closing=False,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "low"

    assert any("already occurred" in reason for reason in assessment.reasons)


def test_parallel_motion_is_low() -> None:
    result = make_cpa_result(
        current_distance_nm=2.0,
        relative_speed_knots=0.0,
        closing_speed_knots=0.0,
        tcpa_minutes=None,
        cpa_distance_nm=2.0,
        future_cpa_distance_nm=2.0,
        is_closing=False,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "low"

    assert assessment.tcpa_minutes is None


def test_current_critical_proximity_takes_priority() -> None:
    result = make_cpa_result(
        current_distance_nm=0.20,
        closing_speed_knots=-5.0,
        tcpa_minutes=-1.0,
        cpa_distance_nm=0.10,
        future_cpa_distance_nm=0.20,
        is_closing=False,
    )

    assessment = assess_collision_risk(
        result,
    )

    assert assessment.risk_level == "critical"

    assert any("Current vessel separation" in reason for reason in assessment.reasons)


def test_custom_thresholds_are_supported() -> None:
    thresholds = CollisionRiskThresholds(
        critical_cpa_nm=0.5,
        critical_tcpa_minutes=20.0,
        high_cpa_nm=1.0,
        high_tcpa_minutes=30.0,
        medium_cpa_nm=2.0,
        medium_tcpa_minutes=60.0,
    )

    result = make_cpa_result(
        tcpa_minutes=15.0,
        cpa_distance_nm=0.4,
        future_cpa_distance_nm=0.4,
    )

    assessment = assess_collision_risk(
        result,
        thresholds,
    )

    assert assessment.risk_level == "critical"


def test_invalid_threshold_order_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="CPA thresholds",
    ):
        CollisionRiskThresholds(
            critical_cpa_nm=1.0,
            high_cpa_nm=0.5,
        )
