from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_NAUTICAL_MILES = 3440.065

REQUIRED_TRAJECTORY_COLUMNS = {
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
}


def _check_required_columns(dataframe: pd.DataFrame) -> None:
    """Verify that the cleaned AIS columns required for a trajectory exist."""

    missing_columns = REQUIRED_TRAJECTORY_COLUMNS - set(dataframe.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Missing required trajectory columns: {missing}")


def haversine_distance_nm(
    latitude_1: pd.Series,
    longitude_1: pd.Series,
    latitude_2: pd.Series,
    longitude_2: pd.Series,
) -> pd.Series:
    """
    Calculate great-circle distance in nautical miles.

    The Haversine formula estimates the shortest distance between
    two positions on Earth's surface.
    """

    latitude_1_rad = np.radians(latitude_1.astype(float))
    longitude_1_rad = np.radians(longitude_1.astype(float))
    latitude_2_rad = np.radians(latitude_2.astype(float))
    longitude_2_rad = np.radians(longitude_2.astype(float))

    latitude_difference = latitude_2_rad - latitude_1_rad
    longitude_difference = longitude_2_rad - longitude_1_rad

    haversine_value = (
        np.sin(latitude_difference / 2) ** 2
        + np.cos(latitude_1_rad)
        * np.cos(latitude_2_rad)
        * np.sin(longitude_difference / 2) ** 2
    )

    # Floating-point calculations can produce tiny values above 1.
    haversine_value = haversine_value.clip(0, 1)

    central_angle = 2 * np.arctan2(
        np.sqrt(haversine_value),
        np.sqrt(1 - haversine_value),
    )

    return EARTH_RADIUS_NAUTICAL_MILES * central_angle


def shortest_angle_change(
    current_angle: pd.Series,
    previous_angle: pd.Series,
) -> pd.Series:
    """
    Calculate the smallest absolute change between two headings.

    For example, changing from 350 degrees to 10 degrees is a
    20-degree change, not a 340-degree change.
    """

    signed_difference = (current_angle - previous_angle + 180) % 360 - 180

    return signed_difference.abs()


def build_trajectory_metrics(
    source: pd.DataFrame,
    mmsi: str | None = None,
) -> pd.DataFrame:
    """
    Create movement metrics for one vessel's ordered AIS observations.

    The input should use SeaGuard's cleaned canonical column names.
    """

    _check_required_columns(source)

    dataframe = source.copy()

    dataframe["mmsi"] = (
        dataframe["mmsi"].astype("string").str.replace(r"\.0$", "", regex=True)
    )

    if mmsi is not None:
        requested_mmsi = str(mmsi)

        dataframe = dataframe.loc[dataframe["mmsi"] == requested_mmsi].copy()

        if dataframe.empty:
            raise ValueError(f"No AIS records found for MMSI {requested_mmsi}.")

    unique_mmsi_count = dataframe["mmsi"].nunique(dropna=True)

    if unique_mmsi_count != 1:
        raise ValueError(
            "Trajectory calculations require exactly one MMSI. "
            f"Found {unique_mmsi_count}."
        )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
        utc=True,
    )

    dataframe["latitude"] = pd.to_numeric(
        dataframe["latitude"],
        errors="coerce",
    )

    dataframe["longitude"] = pd.to_numeric(
        dataframe["longitude"],
        errors="coerce",
    )

    for column in ["sog", "cog", "heading"]:
        if column in dataframe.columns:
            dataframe[column] = pd.to_numeric(
                dataframe[column],
                errors="coerce",
            )

    dataframe = dataframe.dropna(
        subset=[
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
        ]
    )

    dataframe = dataframe.sort_values(
        by="timestamp",
        kind="stable",
    ).reset_index(drop=True)

    dataframe["previous_timestamp"] = dataframe["timestamp"].shift(1)

    dataframe["previous_latitude"] = dataframe["latitude"].shift(1)

    dataframe["previous_longitude"] = dataframe["longitude"].shift(1)

    dataframe["elapsed_seconds"] = (
        dataframe["timestamp"] - dataframe["previous_timestamp"]
    ).dt.total_seconds()

    dataframe["reporting_gap_minutes"] = dataframe["elapsed_seconds"] / 60

    dataframe["nonpositive_time_interval"] = dataframe[
        "elapsed_seconds"
    ].notna() & dataframe["elapsed_seconds"].le(0)

    valid_interval = dataframe["elapsed_seconds"].gt(0)

    dataframe["distance_nm"] = haversine_distance_nm(
        latitude_1=dataframe["previous_latitude"],
        longitude_1=dataframe["previous_longitude"],
        latitude_2=dataframe["latitude"],
        longitude_2=dataframe["longitude"],
    ).where(valid_interval)

    elapsed_hours = dataframe["elapsed_seconds"] / 3600

    dataframe["calculated_speed_knots"] = (
        dataframe["distance_nm"] / elapsed_hours
    ).where(valid_interval)

    dataframe["cumulative_distance_nm"] = dataframe["distance_nm"].fillna(0).cumsum()

    if "sog" in dataframe.columns:
        dataframe["sog_change_knots"] = dataframe["sog"].diff()

        elapsed_minutes = dataframe["elapsed_seconds"] / 60

        dataframe["acceleration_knots_per_minute"] = (
            dataframe["sog_change_knots"] / elapsed_minutes
        ).where(valid_interval)

        dataframe["speed_difference_knots"] = (
            dataframe["calculated_speed_knots"] - dataframe["sog"]
        )

    if "cog" in dataframe.columns:
        dataframe["previous_cog"] = dataframe["cog"].shift(1)

        dataframe["course_change_degrees"] = (
            shortest_angle_change(
                current_angle=dataframe["cog"],
                previous_angle=dataframe["previous_cog"],
            )
        ).where(valid_interval)

    if "heading" in dataframe.columns:
        dataframe["previous_heading"] = dataframe["heading"].shift(1)

        dataframe["heading_change_degrees"] = (
            shortest_angle_change(
                current_angle=dataframe["heading"],
                previous_angle=dataframe["previous_heading"],
            )
        ).where(valid_interval)

    return dataframe
