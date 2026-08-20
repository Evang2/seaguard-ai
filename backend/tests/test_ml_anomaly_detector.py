import numpy as np
import pandas as pd
import pytest

from seaguard.ml.anomaly_detector import (
    AISIsolationForestDetector,
)
from seaguard.ml.feature_engineering import (
    ML_FEATURE_COLUMNS,
)


def make_training_dataframe(
    row_count: int = 100,
) -> pd.DataFrame:
    rng = np.random.default_rng(
        42,
    )

    dataframe = pd.DataFrame(
        {
            "sog": rng.normal(
                12.0,
                1.0,
                row_count,
            ),
            "reporting_gap_minutes": rng.normal(
                1.0,
                0.1,
                row_count,
            ),
            "distance_nm": rng.normal(
                0.2,
                0.02,
                row_count,
            ),
            "calculated_speed_knots": rng.normal(
                12.0,
                1.0,
                row_count,
            ),
            "speed_difference_knots": np.abs(
                rng.normal(
                    0.5,
                    0.2,
                    row_count,
                ),
            ),
            "course_change_degrees": np.abs(
                rng.normal(
                    5.0,
                    2.0,
                    row_count,
                ),
            ),
            "heading_change_degrees": np.abs(
                rng.normal(
                    5.0,
                    2.0,
                    row_count,
                ),
            ),
            "absolute_acceleration_knots_per_minute": np.abs(
                rng.normal(
                    0.2,
                    0.1,
                    row_count,
                ),
            ),
            "turn_rate_degrees_per_minute": np.abs(
                rng.normal(
                    5.0,
                    2.0,
                    row_count,
                ),
            ),
        },
    )

    return dataframe


def test_detector_can_fit_and_score():
    dataframe = make_training_dataframe()

    detector = AISIsolationForestDetector(
        random_state=42,
    )

    result = detector.fit_score(
        dataframe,
    )

    assert detector.is_fitted

    assert len(result) == len(
        dataframe,
    )

    assert "ml_decision_function" in result.columns

    assert "ml_anomaly_score" in result.columns

    assert "ml_is_anomaly" in result.columns

    assert result["ml_decision_function"].notna().all()

    assert result["ml_anomaly_score"].notna().all()

    assert result["ml_is_anomaly"].dtype == bool


def test_more_abnormal_observation_gets_higher_anomaly_score():
    training = make_training_dataframe(
        200,
    )

    detector = AISIsolationForestDetector(
        random_state=42,
    )

    detector.fit(
        training,
    )

    normal = training.iloc[[0]].copy()

    abnormal = normal.copy()

    abnormal.loc[
        abnormal.index[0],
        "sog",
    ] = 65.0

    abnormal.loc[
        abnormal.index[0],
        "reporting_gap_minutes",
    ] = 45.0

    abnormal.loc[
        abnormal.index[0],
        "calculated_speed_knots",
    ] = 90.0

    abnormal.loc[
        abnormal.index[0],
        "speed_difference_knots",
    ] = 50.0

    abnormal.loc[
        abnormal.index[0],
        "course_change_degrees",
    ] = 175.0

    abnormal.loc[
        abnormal.index[0],
        "heading_change_degrees",
    ] = 170.0

    abnormal.loc[
        abnormal.index[0],
        "absolute_acceleration_knots_per_minute",
    ] = 20.0

    abnormal.loc[
        abnormal.index[0],
        "turn_rate_degrees_per_minute",
    ] = 120.0

    normal_result = detector.score(
        normal,
    )

    abnormal_result = detector.score(
        abnormal,
    )

    assert (
        abnormal_result["ml_anomaly_score"].iloc[0]
        > normal_result["ml_anomaly_score"].iloc[0]
    )


def test_detector_handles_missing_values():
    dataframe = make_training_dataframe()

    dataframe.loc[
        0,
        "course_change_degrees",
    ] = np.nan

    dataframe.loc[
        1,
        "heading_change_degrees",
    ] = np.nan

    detector = AISIsolationForestDetector()

    result = detector.fit_score(
        dataframe,
    )

    assert len(result) == len(
        dataframe,
    )

    assert result["ml_anomaly_score"].notna().all()


def test_detector_rejects_missing_feature_columns():
    dataframe = make_training_dataframe()

    dataframe = dataframe.drop(
        columns=[
            "speed_difference_knots",
        ],
    )

    detector = AISIsolationForestDetector()

    with pytest.raises(
        ValueError,
        match=("Missing required ML feature columns"),
    ):
        detector.fit(
            dataframe,
        )


def test_detector_cannot_score_before_fit():
    dataframe = make_training_dataframe()

    detector = AISIsolationForestDetector()

    with pytest.raises(
        RuntimeError,
        match="must be fitted",
    ):
        detector.score(
            dataframe,
        )


def test_feature_configuration_matches_feature_engineering():
    detector = AISIsolationForestDetector()

    assert detector.feature_columns == (ML_FEATURE_COLUMNS)
