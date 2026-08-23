import pytest

from seaguard.collision.geometry import (
    VesselMotion,
    calculate_cpa_tcpa,
)


def test_head_on_encounter_has_zero_cpa() -> None:
    vessel_a = VesselMotion(
        latitude=0.0,
        longitude=0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    vessel_b = VesselMotion(
        latitude=0.0,
        longitude=0.1,
        sog_knots=10.0,
        cog_degrees=270.0,
    )

    result = calculate_cpa_tcpa(
        vessel_a,
        vessel_b,
    )

    assert result.current_distance_nm == pytest.approx(
        6.0,
    )

    assert result.relative_speed_knots == pytest.approx(
        20.0,
    )

    assert result.closing_speed_knots == pytest.approx(
        20.0,
    )

    assert result.tcpa_minutes == pytest.approx(
        18.0,
    )

    assert result.cpa_distance_nm == pytest.approx(
        0.0,
        abs=1e-5,
    )

    assert result.future_cpa_distance_nm == pytest.approx(
        0.0,
        abs=1e-5,
    )

    assert result.is_closing is True


def test_crossing_encounter_reaches_same_point() -> None:
    vessel_a = VesselMotion(
        latitude=0.0,
        longitude=0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    vessel_b = VesselMotion(
        latitude=-0.1,
        longitude=0.1,
        sog_knots=10.0,
        cog_degrees=0.0,
    )

    result = calculate_cpa_tcpa(
        vessel_a,
        vessel_b,
    )

    assert result.current_distance_nm == pytest.approx(
        8.485281,
        rel=1e-5,
    )

    assert result.tcpa_minutes == pytest.approx(
        36.0,
    )

    assert result.cpa_distance_nm == pytest.approx(
        0.0,
        abs=1e-5,
    )

    assert result.is_closing is True


def test_diverging_vessels_have_negative_tcpa() -> None:
    vessel_a = VesselMotion(
        latitude=0.0,
        longitude=0.0,
        sog_knots=10.0,
        cog_degrees=270.0,
    )

    vessel_b = VesselMotion(
        latitude=0.0,
        longitude=0.1,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    result = calculate_cpa_tcpa(
        vessel_a,
        vessel_b,
    )

    assert result.current_distance_nm == pytest.approx(
        6.0,
    )

    assert result.tcpa_minutes == pytest.approx(
        -18.0,
    )

    assert result.cpa_distance_nm == pytest.approx(
        0.0,
        abs=1e-5,
    )

    assert result.future_cpa_distance_nm == pytest.approx(
        6.0,
    )

    assert result.closing_speed_knots == pytest.approx(
        -20.0,
    )

    assert result.is_closing is False


def test_parallel_equal_velocity_has_no_tcpa() -> None:
    vessel_a = VesselMotion(
        latitude=0.0,
        longitude=0.0,
        sog_knots=12.0,
        cog_degrees=90.0,
    )

    vessel_b = VesselMotion(
        latitude=0.0,
        longitude=0.1,
        sog_knots=12.0,
        cog_degrees=90.0,
    )

    result = calculate_cpa_tcpa(
        vessel_a,
        vessel_b,
    )

    assert result.current_distance_nm == pytest.approx(
        6.0,
    )

    assert result.relative_speed_knots == pytest.approx(
        0.0,
        abs=1e-9,
    )

    assert result.tcpa_minutes is None

    assert result.cpa_distance_nm == pytest.approx(
        6.0,
    )

    assert result.future_cpa_distance_nm == pytest.approx(
        6.0,
    )

    assert result.is_closing is False


def test_bearing_from_a_to_b_uses_maritime_convention() -> None:
    vessel_a = VesselMotion(
        latitude=0.0,
        longitude=0.0,
        sog_knots=0.0,
        cog_degrees=0.0,
    )

    vessel_b = VesselMotion(
        latitude=0.0,
        longitude=0.1,
        sog_knots=0.0,
        cog_degrees=0.0,
    )

    result = calculate_cpa_tcpa(
        vessel_a,
        vessel_b,
    )

    assert result.bearing_from_a_to_b_degrees == pytest.approx(90.0)


def test_negative_speed_is_rejected() -> None:
    vessel_a = VesselMotion(
        latitude=0.0,
        longitude=0.0,
        sog_knots=-1.0,
        cog_degrees=0.0,
    )

    vessel_b = VesselMotion(
        latitude=0.0,
        longitude=0.1,
        sog_knots=10.0,
        cog_degrees=180.0,
    )

    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        calculate_cpa_tcpa(
            vessel_a,
            vessel_b,
        )
