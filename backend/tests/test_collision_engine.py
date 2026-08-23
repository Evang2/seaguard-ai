from seaguard.collision.candidates import (
    EncounterVessel,
)
from seaguard.collision.engine import (
    evaluate_collision_encounters,
)


def make_vessel(
    mmsi: str,
    latitude: float,
    longitude: float,
    *,
    sog_knots: float,
    cog_degrees: float,
) -> EncounterVessel:
    return EncounterVessel(
        mmsi=mmsi,
        latitude=latitude,
        longitude=longitude,
        sog_knots=sog_knots,
        cog_degrees=cog_degrees,
    )


def test_critical_head_on_encounter_is_returned() -> None:
    vessel_a = make_vessel(
        "111111111",
        0.0,
        0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    vessel_b = make_vessel(
        "222222222",
        0.0,
        0.05,
        sog_knots=10.0,
        cog_degrees=270.0,
    )

    result = evaluate_collision_encounters(
        [
            vessel_a,
            vessel_b,
        ],
    )

    assert result.assessed_candidate_count == 1

    assert result.encounter_count == 1

    encounter = result.encounters[0]

    assert encounter.risk.risk_level == "critical"

    assert encounter.risk.tcpa_minutes is not None

    assert encounter.risk.tcpa_minutes < 15.0

    assert encounter.risk.cpa_distance_nm < 0.01


def test_low_risk_encounter_is_hidden_by_default() -> None:
    vessel_a = make_vessel(
        "111111111",
        0.0,
        0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    vessel_b = make_vessel(
        "222222222",
        0.0,
        0.01,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    result = evaluate_collision_encounters(
        [
            vessel_a,
            vessel_b,
        ],
    )

    assert result.assessed_candidate_count == 1

    assert result.encounter_count == 0


def test_low_risk_encounter_can_be_included() -> None:
    vessel_a = make_vessel(
        "111111111",
        0.0,
        0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    vessel_b = make_vessel(
        "222222222",
        0.0,
        0.01,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    result = evaluate_collision_encounters(
        [
            vessel_a,
            vessel_b,
        ],
        include_low=True,
    )

    assert result.encounter_count == 1

    assert result.encounters[0].risk.risk_level == "low"

    assert result.low_count == 1


def test_distant_vessels_are_not_assessed() -> None:
    vessel_a = make_vessel(
        "111111111",
        0.0,
        0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    vessel_b = make_vessel(
        "222222222",
        1.0,
        0.0,
        sog_knots=10.0,
        cog_degrees=270.0,
    )

    result = evaluate_collision_encounters(
        [
            vessel_a,
            vessel_b,
        ],
        max_distance_nm=5.0,
    )

    assert result.candidate_search.possible_pair_count == 1

    assert result.candidate_search.candidate_count == 0

    assert result.assessed_candidate_count == 0

    assert result.encounter_count == 0


def test_encounters_are_sorted_by_priority() -> None:
    critical_a = make_vessel(
        "111111111",
        0.0,
        0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    critical_b = make_vessel(
        "222222222",
        0.0,
        0.05,
        sog_knots=10.0,
        cog_degrees=270.0,
    )

    high_a = make_vessel(
        "333333333",
        1.0,
        0.0,
        sog_knots=10.0,
        cog_degrees=90.0,
    )

    high_b = make_vessel(
        "444444444",
        1.0,
        0.10,
        sog_knots=10.0,
        cog_degrees=270.0,
    )

    result = evaluate_collision_encounters(
        [
            high_a,
            high_b,
            critical_a,
            critical_b,
        ],
        max_distance_nm=10.0,
    )

    assert result.encounter_count == 2

    assert [encounter.risk.risk_level for encounter in result.encounters] == [
        "critical",
        "high",
    ]

    assert result.critical_count == 1

    assert result.high_count == 1
