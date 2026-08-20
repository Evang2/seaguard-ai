import pandas as pd
import pytest

from seaguard.ml.feature_engineering import (
    ML_FEATURE_COLUMNS,
    build_ais_features,
)


def test_build_ais_features_calculates_motion_features():
    dataframe = pd.DataFrame(
        {
            "mmsi": [
                "111111111",
                "111111111",
                "111111111",
            ],
            "timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:01:00Z",
                "2026-01-01T00:03:00Z",
            ],
            "latitude": [
                0.0,
                0.0,
                0.0,
            ],
            "longitude": [
                0.0,
                0.01,
                0.03,
            ],
            "sog": [
                10.0,
                12.0,
                8.0,
            ],
            "cog": [
                350.0,
                10.0,
                40.0,
            ],
            "heading": [
                350.0,
                5.0,
                25.0,
            ],
        },
    )

    result = build_ais_features(
        dataframe,
    )

    assert len(result) == 3

    assert all(column in result.columns for column in ML_FEATURE_COLUMNS)

    assert pd.isna(
        result.loc[
            0,
            "reporting_gap_minutes",
        ],
    )

    assert result.loc[
        1,
        "reporting_gap_minutes",
    ] == pytest.approx(1.0)

    assert result.loc[
        2,
        "reporting_gap_minutes",
    ] == pytest.approx(2.0)

    assert result.loc[
        1,
        "course_change_degrees",
    ] == pytest.approx(20.0)

    assert result.loc[
        2,
        "course_change_degrees",
    ] == pytest.approx(30.0)

    assert result.loc[
        1,
        "heading_change_degrees",
    ] == pytest.approx(15.0)

    assert result.loc[
        1,
        "acceleration_knots_per_minute",
    ] == pytest.approx(2.0)

    assert result.loc[
        2,
        "acceleration_knots_per_minute",
    ] == pytest.approx(-2.0)

    assert result.loc[
        2,
        "absolute_acceleration_knots_per_minute",
    ] == pytest.approx(2.0)

    assert (
        result.loc[
            1,
            "distance_nm",
        ]
        > 0.0
    )

    assert (
        result.loc[
            1,
            "calculated_speed_knots",
        ]
        > 0.0
    )


def test_features_do_not_cross_vessel_boundaries():
    dataframe = pd.DataFrame(
        {
            "mmsi": [
                "111111111",
                "222222222",
                "111111111",
                "222222222",
            ],
            "timestamp": [
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:01:00Z",
                "2026-01-01T00:02:00Z",
            ],
            "latitude": [
                0.0,
                10.0,
                0.0,
                10.0,
            ],
            "longitude": [
                0.0,
                20.0,
                0.01,
                20.01,
            ],
            "sog": [
                10.0,
                5.0,
                11.0,
                6.0,
            ],
            "cog": [
                90.0,
                180.0,
                100.0,
                190.0,
            ],
            "heading": [
                90.0,
                180.0,
                100.0,
                190.0,
            ],
        },
    )

    result = build_ais_features(
        dataframe,
    )

    first_reports = result.groupby(
        "mmsi",
        sort=False,
    ).head(1)

    assert first_reports["reporting_gap_minutes"].isna().all()

    assert first_reports["distance_nm"].isna().all()

    assert first_reports["course_change_degrees"].isna().all()


def test_missing_required_columns_raise_error():
    dataframe = pd.DataFrame(
        {
            "mmsi": [
                "111111111",
            ],
            "timestamp": [
                "2026-01-01T00:00:00Z",
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="Missing required AIS columns",
    ):
        build_ais_features(
            dataframe,
        )
