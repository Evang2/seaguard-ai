from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from seaguard.ais.anomalies import detect_rule_based_anomalies
from seaguard.db.models import AISMessage, AnomalyAlert, Vessel
from seaguard.ingestion.analytics import (
    AnalyticsStageResult,
    IngestionAnalyticsContext,
    IngestionAnalyticsSummary,
    run_ingestion_analytics,
)

EARTH_RADIUS_NM = 3440.065

SOURCE_KEY_COLUMNS = {
    "mmsi",
    "timestamp",
}


def _normalize_mmsi(
    values: pd.Series,
) -> pd.Series:
    """Normalize MMSI values into nine-digit strings where possible."""

    return (
        values.astype("string")
        .str.strip()
        .str.replace(
            r"\.0$",
            "",
            regex=True,
        )
    )


def _source_message_keys(
    source_file: Path,
) -> set[tuple[str, datetime]]:
    """
    Return normalized MMSI/timestamp identities requested by one source CSV.

    Invalid rows are ignored here because the AIS importer has already applied
    its own validation before this analytics stage runs.
    """

    source = pd.read_csv(
        source_file,
        usecols=lambda column: column in SOURCE_KEY_COLUMNS,
        dtype={
            "mmsi": "string",
        },
    )

    missing = SOURCE_KEY_COLUMNS - set(source.columns)

    if missing:
        names = ", ".join(sorted(missing))

        raise ValueError(
            f"Incoming AIS file is missing analytics identity columns: {names}"
        )

    source["mmsi"] = _normalize_mmsi(source["mmsi"])

    source["timestamp"] = pd.to_datetime(
        source["timestamp"],
        errors="coerce",
        utc=True,
    )

    valid = source.loc[
        source["mmsi"].str.fullmatch(
            r"\d{9}",
            na=False,
        )
        & source["timestamp"].notna(),
        [
            "mmsi",
            "timestamp",
        ],
    ]

    keys: set[tuple[str, datetime]] = set()

    for row in valid.itertuples(index=False):
        timestamp = row.timestamp

        if isinstance(
            timestamp,
            pd.Timestamp,
        ):
            timestamp = timestamp.to_pydatetime()

        keys.add(
            (
                str(row.mmsi),
                timestamp,
            )
        )

    return keys


def _angular_difference(
    current: pd.Series,
    previous: pd.Series,
) -> pd.Series:
    """
    Return absolute circular-angle difference in degrees.

    359 -> 1 degrees is therefore a 2-degree change rather than 358.
    """

    difference = (current - previous).abs()

    return np.minimum(
        difference,
        360.0 - difference,
    )


def _haversine_nm(
    latitude: pd.Series,
    longitude: pd.Series,
    previous_latitude: pd.Series,
    previous_longitude: pd.Series,
) -> pd.Series:
    """Return great-circle distance from the previous point in nautical miles."""

    lat1 = np.radians(previous_latitude.astype("float64"))
    lon1 = np.radians(previous_longitude.astype("float64"))
    lat2 = np.radians(latitude.astype("float64"))
    lon2 = np.radians(longitude.astype("float64"))

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    haversine = np.sin(delta_lat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * (
        np.sin(delta_lon / 2.0) ** 2
    )

    central_angle = 2.0 * np.arctan2(
        np.sqrt(haversine),
        np.sqrt(
            np.maximum(
                0.0,
                1.0 - haversine,
            )
        ),
    )

    return pd.Series(
        EARTH_RADIUS_NM * central_angle,
        index=latitude.index,
        dtype="float64",
    )


def build_live_motion_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Derive trajectory context required by SeaGuard's rule detector.

    Input can contain multiple MMSIs. All deltas are calculated strictly
    inside each vessel group and in timestamp/id order.
    """

    required = {
        "id",
        "mmsi",
        "timestamp",
        "latitude",
        "longitude",
        "sog",
        "cog",
        "heading",
    }

    missing = required - set(dataframe.columns)

    if missing:
        names = ", ".join(sorted(missing))

        raise ValueError(f"Live anomaly context is missing required columns: {names}")

    if dataframe.empty:
        result = dataframe.copy()

        for column in (
            "elapsed_seconds",
            "reporting_gap_minutes",
            "distance_nm",
            "calculated_speed_knots",
            "speed_difference_knots",
            "course_change_degrees",
            "heading_change_degrees",
            "acceleration_knots_per_minute",
            "absolute_acceleration_knots_per_minute",
            "turn_rate_degrees_per_minute",
        ):
            result[column] = pd.Series(dtype="float64")

        result["nonpositive_time_interval"] = pd.Series(dtype="bool")

        return result

    result = dataframe.copy()

    result["mmsi"] = _normalize_mmsi(result["mmsi"])

    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        errors="coerce",
        utc=True,
    )

    for column in (
        "latitude",
        "longitude",
        "sog",
        "cog",
        "heading",
    ):
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result = result.sort_values(
        [
            "mmsi",
            "timestamp",
            "id",
        ]
    ).reset_index(drop=True)

    grouped = result.groupby(
        "mmsi",
        sort=False,
        dropna=False,
    )

    previous_timestamp = grouped["timestamp"].shift(1)

    result["elapsed_seconds"] = (
        result["timestamp"] - previous_timestamp
    ).dt.total_seconds()

    result["reporting_gap_minutes"] = result["elapsed_seconds"] / 60.0

    previous_latitude = grouped["latitude"].shift(1)
    previous_longitude = grouped["longitude"].shift(1)

    result["distance_nm"] = _haversine_nm(
        result["latitude"],
        result["longitude"],
        previous_latitude,
        previous_longitude,
    )

    positive_elapsed = result["elapsed_seconds"] > 0.0

    result["calculated_speed_knots"] = np.where(
        positive_elapsed,
        result["distance_nm"] / (result["elapsed_seconds"] / 3600.0),
        np.nan,
    )

    result["speed_difference_knots"] = (
        result["sog"] - result["calculated_speed_knots"]
    ).abs()

    previous_cog = grouped["cog"].shift(1)

    result["course_change_degrees"] = _angular_difference(
        result["cog"],
        previous_cog,
    )

    previous_heading = grouped["heading"].shift(1)

    result["heading_change_degrees"] = _angular_difference(
        result["heading"],
        previous_heading,
    )

    previous_sog = grouped["sog"].shift(1)

    result["acceleration_knots_per_minute"] = np.where(
        positive_elapsed,
        (result["sog"] - previous_sog) / result["reporting_gap_minutes"],
        np.nan,
    )

    result["absolute_acceleration_knots_per_minute"] = result[
        "acceleration_knots_per_minute"
    ].abs()

    valid_turn_rate = result["reporting_gap_minutes"].notna() & result[
        "reporting_gap_minutes"
    ].gt(0.0)

    result["turn_rate_degrees_per_minute"] = np.where(
        valid_turn_rate,
        result["course_change_degrees"] / result["reporting_gap_minutes"],
        np.nan,
    )

    result["nonpositive_time_interval"] = result["elapsed_seconds"].notna() & (
        result["elapsed_seconds"] <= 0.0
    )

    return result


def _load_affected_history(
    session: Session,
    keys: set[tuple[str, datetime]],
) -> pd.DataFrame:
    """
    Load vessel history through the newest timestamp in this incoming file.

    Older observations are necessary to calculate reporting gaps, speed,
    course change, heading change, and acceleration for newly inserted rows.
    """

    if not keys:
        return pd.DataFrame(
            columns=[
                "id",
                "mmsi",
                "timestamp",
                "latitude",
                "longitude",
                "sog",
                "cog",
                "heading",
            ]
        )

    mmsis = sorted({mmsi for mmsi, _ in keys})

    maximum_timestamp = max(timestamp for _, timestamp in keys)

    rows = session.execute(
        select(
            AISMessage.id,
            Vessel.mmsi,
            AISMessage.timestamp,
            AISMessage.latitude,
            AISMessage.longitude,
            AISMessage.sog,
            AISMessage.cog,
            AISMessage.heading,
        )
        .join(
            Vessel,
            Vessel.id == AISMessage.vessel_id,
        )
        .where(
            Vessel.mmsi.in_(mmsis),
            AISMessage.timestamp <= maximum_timestamp,
        )
        .order_by(
            Vessel.mmsi.asc(),
            AISMessage.timestamp.asc(),
            AISMessage.id.asc(),
        )
    ).all()

    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "mmsi",
            "timestamp",
            "latitude",
            "longitude",
            "sog",
            "cog",
            "heading",
        ],
    )


def _filter_alerts_to_keys(
    alerts: pd.DataFrame,
    keys: set[tuple[str, datetime]],
) -> pd.DataFrame:
    """Keep only alerts belonging to the currently imported source file."""

    if alerts.empty or not keys:
        return alerts.iloc[0:0].copy()

    filtered = alerts.copy()

    filtered["mmsi"] = _normalize_mmsi(filtered["mmsi"])

    filtered["timestamp"] = pd.to_datetime(
        filtered["timestamp"],
        errors="coerce",
        utc=True,
    )

    mask = [
        (
            str(row.mmsi),
            (
                row.timestamp.to_pydatetime()
                if isinstance(
                    row.timestamp,
                    pd.Timestamp,
                )
                else row.timestamp
            ),
        )
        in keys
        for row in filtered.itertuples(index=False)
    ]

    return filtered.loc[mask].reset_index(drop=True)


def _message_identity_map(
    session: Session,
    alerts: pd.DataFrame,
) -> dict[
    tuple[str, datetime],
    tuple[int, int],
]:
    """
    Map (MMSI, timestamp) to (AIS message id, vessel id).
    """

    if alerts.empty:
        return {}

    mmsis = alerts["mmsi"].astype(str).unique().tolist()

    timestamps: list[datetime] = []

    for value in alerts["timestamp"].dropna().unique().tolist():
        timestamp = pd.Timestamp(value)

        timestamps.append(timestamp.to_pydatetime())

    rows = session.execute(
        select(
            Vessel.mmsi,
            AISMessage.timestamp,
            AISMessage.id,
            AISMessage.vessel_id,
        )
        .join(
            Vessel,
            Vessel.id == AISMessage.vessel_id,
        )
        .where(
            Vessel.mmsi.in_(mmsis),
            AISMessage.timestamp.in_(timestamps),
        )
    ).all()

    return {
        (
            str(mmsi),
            timestamp,
        ): (
            message_id,
            vessel_id,
        )
        for (
            mmsi,
            timestamp,
            message_id,
            vessel_id,
        ) in rows
    }


def _optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (
        TypeError,
        ValueError,
    ):
        pass

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def _alert_records(
    alerts: pd.DataFrame,
    identity_map: dict[
        tuple[str, datetime],
        tuple[int, int],
    ],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for row in alerts.itertuples(index=False):
        timestamp = row.timestamp

        if isinstance(
            timestamp,
            pd.Timestamp,
        ):
            timestamp = timestamp.to_pydatetime()

        identity = identity_map.get(
            (
                str(row.mmsi),
                timestamp,
            )
        )

        if identity is None:
            continue

        (
            ais_message_id,
            vessel_id,
        ) = identity

        records.append(
            {
                "ais_message_id": (ais_message_id),
                "vessel_id": (vessel_id),
                "observed_at": (timestamp),
                "anomaly_type": (str(row.anomaly_type)),
                "severity": (str(row.severity)),
                "metric_name": (str(row.metric_name)),
                "metric_value": (_optional_float(row.metric_value)),
                "threshold": (_optional_float(row.threshold)),
                "message": (str(row.message)),
            }
        )

    return records


def _batches(
    records: list[dict[str, Any]],
    size: int,
) -> Iterable[list[dict[str, Any]]]:
    if size <= 0:
        raise ValueError("insert_batch_size must be positive.")

    for start in range(
        0,
        len(records),
        size,
    ):
        yield records[start : start + size]


def _upsert_alerts(
    session: Session,
    records: list[dict[str, Any]],
    *,
    insert_batch_size: int,
) -> int:
    """
    Upsert anomaly alerts using the database's message/type identity.
    """

    written = 0

    for batch in _batches(
        records,
        insert_batch_size,
    ):
        statement = insert(AnomalyAlert).values(batch)

        excluded = statement.excluded

        statement = statement.on_conflict_do_update(
            index_elements=[
                AnomalyAlert.ais_message_id,
                AnomalyAlert.anomaly_type,
            ],
            set_={
                "vessel_id": (excluded.vessel_id),
                "observed_at": (excluded.observed_at),
                "severity": (excluded.severity),
                "metric_name": (excluded.metric_name),
                "metric_value": (excluded.metric_value),
                "threshold": (excluded.threshold),
                "message": (excluded.message),
            },
        )

        session.execute(statement)

        written += len(batch)

    return written


def persist_live_rule_anomalies(
    session: Session,
    context: IngestionAnalyticsContext,
    *,
    insert_batch_size: int = 1_000,
) -> AnalyticsStageResult:
    """
    Detect and persist rule-based anomalies for one imported AIS file.

    Detection is calculated with each affected vessel's historical context,
    but only alerts belonging to rows from the current source file are
    persisted by this invocation.
    """

    incoming_keys = _source_message_keys(context.source_file)

    history = _load_affected_history(
        session,
        incoming_keys,
    )

    if not incoming_keys or history.empty:
        return AnalyticsStageResult(
            name="rule_anomalies",
            processed=0,
            created=0,
        )

    features = build_live_motion_features(history)

    _, all_alerts = detect_rule_based_anomalies(features)

    incoming_alerts = _filter_alerts_to_keys(
        all_alerts,
        incoming_keys,
    )

    identity_map = _message_identity_map(
        session,
        incoming_alerts,
    )

    records = _alert_records(
        incoming_alerts,
        identity_map,
    )

    written = _upsert_alerts(
        session,
        records,
        insert_batch_size=(insert_batch_size),
    )

    session.commit()

    return AnalyticsStageResult(
        name="rule_anomalies",
        processed=len(incoming_keys),
        created=written,
    )


def run_live_analytics(
    session: Session,
    context: IngestionAnalyticsContext,
) -> IngestionAnalyticsSummary:
    """
    v1 live analytics runner.

    10B-B1 contains the deterministic rule stage.
    ML/hybrid-risk and collision stages are intentionally added next,
    once this live persistence path is verified end-to-end.
    """

    return run_ingestion_analytics(
        session,
        context,
        stages=(persist_live_rule_anomalies,),
    )
