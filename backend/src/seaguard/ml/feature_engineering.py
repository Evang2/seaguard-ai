from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_NAUTICAL_MILES = 3440.065

REQUIRED_COLUMNS = {
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
    "sog",
    "cog",
    "heading",
}


ML_FEATURE_COLUMNS = [
    "sog",
    "reporting_gap_minutes",
    "distance_nm",
    "calculated_speed_knots",
    "speed_difference_knots",
    "course_change_degrees",
    "heading_change_degrees",
    "absolute_acceleration_knots_per_minute",
    "turn_rate_degrees_per_minute",
]


def _validate_columns(dataframe: pd.DataFrame) -> None:
    missing_columns = REQUIRED_COLUMNS.difference(
        dataframe.columns,
    )

    if missing_columns:
        missing = ", ".join(
            sorted(missing_columns),
        )

        raise ValueError(
            f"Missing required AIS columns: {missing}",
        )


def _circular_change(
    current: pd.Series,
    previous: pd.Series,
) -> pd.Series:
    """
    Calculate the smallest angular difference.

    Example:
        350 degrees -> 10 degrees = 20 degrees,
        not 340 degrees.
    """

    delta = (current - previous + 180.0) % 360.0 - 180.0

    return delta.abs()


def _haversine_distance_nm(
    latitude_1: pd.Series,
    longitude_1: pd.Series,
    latitude_2: pd.Series,
    longitude_2: pd.Series,
) -> np.ndarray:
    """
    Calculate great-circle distance in nautical miles.
    """

    lat_1 = np.radians(
        latitude_1.to_numpy(
            dtype=float,
        ),
    )

    lon_1 = np.radians(
        longitude_1.to_numpy(
            dtype=float,
        ),
    )

    lat_2 = np.radians(
        latitude_2.to_numpy(
            dtype=float,
        ),
    )

    lon_2 = np.radians(
        longitude_2.to_numpy(
            dtype=float,
        ),
    )

    delta_latitude = lat_2 - lat_1
    delta_longitude = lon_2 - lon_1

    haversine = (
        np.sin(delta_latitude / 2.0) ** 2
        + np.cos(lat_1) * np.cos(lat_2) * np.sin(delta_longitude / 2.0) ** 2
    )

    haversine = np.clip(
        haversine,
        0.0,
        1.0,
    )

    central_angle = 2.0 * np.arcsin(
        np.sqrt(haversine),
    )

    return EARTH_RADIUS_NAUTICAL_MILES * central_angle


def build_ais_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build motion and reporting features from AIS positions.

    Features are calculated independently for every MMSI so that
    measurements from different vessels never affect one another.
    """

    _validate_columns(dataframe)

    features = dataframe.copy()

    features["timestamp"] = pd.to_datetime(
        features["timestamp"],
        utc=True,
        errors="coerce",
    )

    numeric_columns = [
        "latitude",
        "longitude",
        "sog",
        "cog",
        "heading",
    ]

    for column in numeric_columns:
        features[column] = pd.to_numeric(
            features[column],
            errors="coerce",
        )

    features.loc[
        (features["latitude"] < -90.0) | (features["latitude"] > 90.0),
        "latitude",
    ] = np.nan

    features.loc[
        (features["longitude"] < -180.0) | (features["longitude"] > 180.0),
        "longitude",
    ] = np.nan

    features.loc[
        features["sog"] < 0.0,
        "sog",
    ] = np.nan

    features.loc[
        (features["cog"] < 0.0) | (features["cog"] >= 360.0),
        "cog",
    ] = np.nan

    features.loc[
        (features["heading"] < 0.0) | (features["heading"] >= 360.0),
        "heading",
    ] = np.nan

    features = features.sort_values(
        ["mmsi", "timestamp"],
        kind="stable",
    ).reset_index(drop=True)

    grouped = features.groupby(
        "mmsi",
        sort=False,
    )

    features["elapsed_seconds"] = grouped["timestamp"].diff().dt.total_seconds()

    features["reporting_gap_minutes"] = features["elapsed_seconds"] / 60.0

    previous_latitude = grouped["latitude"].shift()

    previous_longitude = grouped["longitude"].shift()

    features["distance_nm"] = _haversine_distance_nm(
        previous_latitude,
        previous_longitude,
        features["latitude"],
        features["longitude"],
    )

    missing_position = (
        previous_latitude.isna()
        | previous_longitude.isna()
        | features["latitude"].isna()
        | features["longitude"].isna()
    )

    features.loc[
        missing_position,
        "distance_nm",
    ] = np.nan

    positive_interval = features["elapsed_seconds"] > 0.0

    elapsed_hours = features["elapsed_seconds"] / 3600.0

    features["calculated_speed_knots"] = features["distance_nm"] / elapsed_hours

    features.loc[
        ~positive_interval,
        "calculated_speed_knots",
    ] = np.nan

    features["speed_difference_knots"] = (
        features["calculated_speed_knots"] - features["sog"]
    ).abs()

    previous_course = grouped["cog"].shift()

    features["course_change_degrees"] = _circular_change(
        features["cog"],
        previous_course,
    )

    previous_heading = grouped["heading"].shift()

    features["heading_change_degrees"] = _circular_change(
        features["heading"],
        previous_heading,
    )

    speed_change = grouped["sog"].diff()

    features["acceleration_knots_per_minute"] = (
        speed_change / features["reporting_gap_minutes"]
    )

    features.loc[
        ~positive_interval,
        "acceleration_knots_per_minute",
    ] = np.nan

    features["absolute_acceleration_knots_per_minute"] = features[
        "acceleration_knots_per_minute"
    ].abs()

    features["turn_rate_degrees_per_minute"] = (
        features["course_change_degrees"] / features["reporting_gap_minutes"]
    )

    features.loc[
        ~positive_interval,
        "turn_rate_degrees_per_minute",
    ] = np.nan

    return features
