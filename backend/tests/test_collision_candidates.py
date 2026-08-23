import pytest

from seaguard.collision.candidates import (
    EncounterVessel,
    generate_encounter_candidates,
)


def make_vessel(
    mmsi: str,
    latitude: float,
    longitude: float,
    *,
    sog_knots: float = 10.0,
    cog_degrees: float = 90.0,
) -> EncounterVessel:
    return EncounterVessel(
        mmsi=mmsi,
        latitude=latitude,
        longitude=longitude,
        sog_knots=sog_knots,
        cog_degrees=cog_degrees,
    )


def test_nearby_vessels_become_candidate() -> None:
    vessels = [
        make_vessel(
            "111111111",
            40.0,
            -74.0,
        ),
        make_vessel(
            "222222222",
            40.0,
            -73.99,
        ),
    ]

    result = generate_encounter_candidates(
        vessels,
        max_distance_nm=5.0,
    )

    assert result.candidate_count == 1

    candidate = result.candidates[0]

    assert candidate.vessel_a.mmsi == "111111111"

    assert candidate.vessel_b.mmsi == "222222222"

    assert candidate.current_distance_nm < 1.0


def test_distant_vessels_are_excluded() -> None:
    vessels = [
        make_vessel(
            "111111111",
            40.0,
            -74.0,
        ),
        make_vessel(
            "222222222",
            41.0,
            -74.0,
        ),
    ]

    result = generate_encounter_candidates(
        vessels,
        max_distance_nm=5.0,
    )

    assert result.candidate_count == 0


def test_candidate_search_reports_pair_metrics() -> None:
    vessels = [
        make_vessel(
            "111111111",
            40.0,
            -74.0,
        ),
        make_vessel(
            "222222222",
            40.01,
            -74.0,
        ),
        make_vessel(
            "333333333",
            45.0,
            -74.0,
        ),
    ]

    result = generate_encounter_candidates(
        vessels,
        max_distance_nm=5.0,
    )

    assert result.vessel_count == 3

    assert result.possible_pair_count == 3

    assert result.candidate_count == 1

    assert result.distance_checked_pair_count < result.possible_pair_count


def test_stationary_vessel_can_be_candidate() -> None:
    vessels = [
        make_vessel(
            "111111111",
            40.0,
            -74.0,
            sog_knots=0.0,
        ),
        make_vessel(
            "222222222",
            40.0,
            -73.99,
            sog_knots=12.0,
        ),
    ]

    result = generate_encounter_candidates(
        vessels,
        max_distance_nm=5.0,
    )

    assert result.candidate_count == 1


def test_duplicate_mmsi_is_rejected() -> None:
    vessels = [
        make_vessel(
            "111111111",
            40.0,
            -74.0,
        ),
        make_vessel(
            "111111111",
            40.01,
            -74.0,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="one state per MMSI",
    ):
        generate_encounter_candidates(
            vessels,
        )


def test_invalid_search_distance_is_rejected() -> None:
    vessel = make_vessel(
        "111111111",
        40.0,
        -74.0,
    )

    with pytest.raises(
        ValueError,
        match="positive finite",
    ):
        generate_encounter_candidates(
            [vessel],
            max_distance_nm=0.0,
        )


def test_antimeridian_pair_is_detected() -> None:
    vessels = [
        make_vessel(
            "111111111",
            0.0,
            179.99,
        ),
        make_vessel(
            "222222222",
            0.0,
            -179.99,
        ),
    ]

    result = generate_encounter_candidates(
        vessels,
        max_distance_nm=2.0,
    )

    assert result.candidate_count == 1

    assert result.candidates[0].current_distance_nm < 2.0
