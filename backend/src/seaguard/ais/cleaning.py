from __future__ import annotations

import re
from typing import Any

import pandas as pd

COLUMN_NAME_MAP = {
    "mmsi": "mmsi",
    "basedatetime": "timestamp",
    "lat": "latitude",
    "lon": "longitude",
    "sog": "sog",
    "cog": "cog",
    "heading": "heading",
    "vesselname": "vessel_name",
    "imo": "imo",
    "callsign": "call_sign",
    "vesseltype": "vessel_type",
    "status": "navigation_status",
    "length": "length_m",
    "width": "width_m",
    "draft": "draft_m",
    "cargo": "cargo",
    "transceiverclass": "transceiver_class",
}


REQUIRED_COLUMNS = {
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
}


NUMERIC_COLUMNS = [
    "latitude",
    "longitude",
    "sog",
    "cog",
    "heading",
    "vessel_type",
    "navigation_status",
    "length_m",
    "width_m",
    "draft_m",
]


TEXT_COLUMNS = [
    "mmsi",
    "vessel_name",
    "imo",
    "call_sign",
    "cargo",
    "transceiver_class",
]


def _normalized_column_key(column: str) -> str:
    """Create a comparison key from a source column name."""

    return re.sub(
        pattern=r"[^a-z0-9]",
        repl="",
        string=column.lower(),
    )


def normalize_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Rename known NOAA columns to SeaGuard's canonical names.

    Unknown columns are preserved under their original names.
    """

    rename_map: dict[str, str] = {}

    for column in dataframe.columns:
        key = _normalized_column_key(str(column))
        canonical_name = COLUMN_NAME_MAP.get(key)

        if canonical_name is not None:
            rename_map[column] = canonical_name

    normalized = dataframe.rename(columns=rename_map).copy()

    missing_columns = REQUIRED_COLUMNS - set(normalized.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Missing required AIS columns: {missing}")

    return normalized


def clean_ais_dataframe(
    source: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    """
    Clean AIS data and split it into accepted and rejected records.

    The original DataFrame is not modified.
    """

    dataframe = normalize_columns(source)

    for column in TEXT_COLUMNS:
        if column not in dataframe.columns:
            continue

        dataframe[column] = (
            dataframe[column].astype("string").str.strip().replace("", pd.NA)
        )

    # Pandas can sometimes read MMSI as a float when missing values exist.
    # This removes a trailing ".0", such as 123456789.0.
    dataframe["mmsi"] = dataframe["mmsi"].str.replace(
        r"\.0$",
        "",
        regex=True,
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
        utc=True,
    )

    for column in NUMERIC_COLUMNS:
        if column not in dataframe.columns:
            continue

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    # Core field validation.
    dataframe["invalid_mmsi"] = ~dataframe["mmsi"].str.fullmatch(
        r"\d{9}",
        na=False,
    )

    dataframe["invalid_timestamp"] = dataframe["timestamp"].isna()

    dataframe["invalid_latitude"] = dataframe["latitude"].isna() | ~dataframe[
        "latitude"
    ].between(-90, 90)

    dataframe["invalid_longitude"] = dataframe["longitude"].isna() | ~dataframe[
        "longitude"
    ].between(-180, 180)

    # Speed over ground validation.
    dataframe["sog_unavailable"] = False
    dataframe["sog_invalid"] = False

    if "sog" in dataframe.columns:
        dataframe["sog_unavailable"] = dataframe["sog"].eq(102.3)

        dataframe["sog_invalid"] = dataframe["sog"].lt(0) | dataframe["sog"].gt(102.3)

        dataframe.loc[
            (dataframe["sog_unavailable"] | dataframe["sog_invalid"]),
            "sog",
        ] = pd.NA

    # Course over ground validation.
    dataframe["cog_unavailable"] = False
    dataframe["cog_invalid"] = False

    if "cog" in dataframe.columns:
        dataframe["cog_unavailable"] = dataframe["cog"].eq(360.0)

        dataframe["cog_invalid"] = dataframe["cog"].lt(0) | dataframe["cog"].gt(360.0)

        dataframe.loc[
            (dataframe["cog_unavailable"] | dataframe["cog_invalid"]),
            "cog",
        ] = pd.NA

    # True-heading validation.
    dataframe["heading_unavailable"] = False
    dataframe["heading_invalid"] = False

    if "heading" in dataframe.columns:
        dataframe["heading_unavailable"] = dataframe["heading"].eq(511)

        dataframe["heading_invalid"] = dataframe["heading"].lt(0) | (
            dataframe["heading"].ge(360) & ~dataframe["heading_unavailable"]
        )

        dataframe.loc[
            (dataframe["heading_unavailable"] | dataframe["heading_invalid"]),
            "heading",
        ] = pd.NA

    core_issue_columns = [
        "invalid_mmsi",
        "invalid_timestamp",
        "invalid_latitude",
        "invalid_longitude",
    ]

    dataframe["is_valid_core_record"] = ~dataframe[core_issue_columns].any(axis=1)

    duplicate_key = [
        "mmsi",
        "timestamp",
        "latitude",
        "longitude",
    ]

    dataframe["duplicate_record"] = dataframe.duplicated(
        subset=duplicate_key,
        keep="first",
    )

    rejected = dataframe.loc[~dataframe["is_valid_core_record"]].copy()

    cleaned = dataframe.loc[
        dataframe["is_valid_core_record"] & ~dataframe["duplicate_record"]
    ].copy()

    cleaned = cleaned.sort_values(
        by=["mmsi", "timestamp"],
        kind="stable",
    ).reset_index(drop=True)

    rejected = rejected.reset_index(drop=True)

    report: dict[str, Any] = {
        "rows_read": int(len(dataframe)),
        "rows_clean": int(len(cleaned)),
        "rows_rejected": int(len(rejected)),
        "duplicates_removed": int(dataframe["duplicate_record"].sum()),
        "unique_mmsi_clean": int(cleaned["mmsi"].nunique(dropna=True)),
        "invalid_mmsi": int(dataframe["invalid_mmsi"].sum()),
        "invalid_timestamp": int(dataframe["invalid_timestamp"].sum()),
        "invalid_latitude": int(dataframe["invalid_latitude"].sum()),
        "invalid_longitude": int(dataframe["invalid_longitude"].sum()),
        "sog_unavailable": int(dataframe["sog_unavailable"].sum()),
        "sog_invalid": int(dataframe["sog_invalid"].sum()),
        "cog_unavailable": int(dataframe["cog_unavailable"].sum()),
        "cog_invalid": int(dataframe["cog_invalid"].sum()),
        "heading_unavailable": int(dataframe["heading_unavailable"].sum()),
        "heading_invalid": int(dataframe["heading_invalid"].sum()),
        "earliest_timestamp": (
            cleaned["timestamp"].min().isoformat() if not cleaned.empty else None
        ),
        "latest_timestamp": (
            cleaned["timestamp"].max().isoformat() if not cleaned.empty else None
        ),
    }

    return cleaned, rejected, report
