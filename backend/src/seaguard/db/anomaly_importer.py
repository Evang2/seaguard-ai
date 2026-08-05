from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from seaguard.db.models import (
    AISMessage,
    AnomalyAlert,
    Vessel,
)

REQUIRED_ALERT_COLUMNS = {
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
    "anomaly_type",
    "severity",
    "metric_name",
    "message",
}

TEXT_ALERT_COLUMNS = [
    "mmsi",
    "anomaly_type",
    "severity",
    "metric_name",
    "message",
]

MessageIdentity = tuple[
    str,
    datetime,
    float,
    float,
]

MessageLink = tuple[int, int]


@dataclass(frozen=True, slots=True)
class AlertImportSummary:
    """Results from one anomaly-alert import."""

    source_file: str
    rows_read: int
    rows_imported: int
    rows_rejected: int
    messages_not_found: int
    duplicates_skipped: int


def _is_missing(value: Any) -> bool:
    """Return whether a scalar value is missing."""

    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _optional_float(value: Any) -> float | None:
    """Convert a value to float or None."""

    if _is_missing(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _identity_key(
    mmsi: Any,
    timestamp: Any,
    latitude: Any,
    longitude: Any,
) -> MessageIdentity:
    """Create the exact key used to identify an AIS message."""

    if isinstance(timestamp, pd.Timestamp):
        timestamp_value = timestamp.to_pydatetime()
    elif isinstance(timestamp, datetime):
        timestamp_value = timestamp
    else:
        timestamp_value = pd.Timestamp(timestamp).to_pydatetime()

    return (
        str(mmsi),
        timestamp_value,
        float(latitude),
        float(longitude),
    )


def _prepare_alert_chunk(
    source: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Normalize and validate an anomaly-alert CSV chunk."""

    missing_columns = REQUIRED_ALERT_COLUMNS - set(source.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Missing required alert columns: {missing}")

    dataframe = source.copy()

    for column in TEXT_ALERT_COLUMNS:
        dataframe[column] = (
            dataframe[column].astype("string").str.strip().replace("", pd.NA)
        )

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

    dataframe["latitude"] = pd.to_numeric(
        dataframe["latitude"],
        errors="coerce",
    )

    dataframe["longitude"] = pd.to_numeric(
        dataframe["longitude"],
        errors="coerce",
    )

    for column in ["metric_value", "threshold"]:
        if column not in dataframe.columns:
            dataframe[column] = pd.NA

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    valid_rows = (
        dataframe["mmsi"].str.fullmatch(
            r"\d{9}",
            na=False,
        )
        & dataframe["timestamp"].notna()
        & dataframe["latitude"].between(-90, 90)
        & dataframe["longitude"].between(-180, 180)
        & dataframe["anomaly_type"].notna()
        & dataframe["severity"].notna()
        & dataframe["metric_name"].notna()
        & dataframe["message"].notna()
    )

    rejected_count = int((~valid_rows).sum())

    prepared = dataframe.loc[valid_rows].reset_index(drop=True)

    return prepared, rejected_count


def _load_message_links(
    session: Session,
    dataframe: pd.DataFrame,
) -> dict[MessageIdentity, MessageLink]:
    """Load AIS message and vessel IDs for alert identities."""

    if dataframe.empty:
        return {}

    identities = {
        _identity_key(
            row.mmsi,
            row.timestamp,
            row.latitude,
            row.longitude,
        )
        for row in dataframe.itertuples(index=False)
    }

    identity_expression = tuple_(
        Vessel.mmsi,
        AISMessage.timestamp,
        AISMessage.latitude,
        AISMessage.longitude,
    )

    rows = session.execute(
        select(
            Vessel.mmsi,
            AISMessage.timestamp,
            AISMessage.latitude,
            AISMessage.longitude,
            AISMessage.id,
            AISMessage.vessel_id,
        )
        .join(
            Vessel,
            Vessel.id == AISMessage.vessel_id,
        )
        .where(identity_expression.in_(list(identities)))
    ).all()

    return {
        _identity_key(
            mmsi,
            timestamp,
            latitude,
            longitude,
        ): (
            message_id,
            vessel_id,
        )
        for (
            mmsi,
            timestamp,
            latitude,
            longitude,
            message_id,
            vessel_id,
        ) in rows
    }


def _build_alert_records(
    dataframe: pd.DataFrame,
    message_links: dict[
        MessageIdentity,
        MessageLink,
    ],
) -> tuple[list[dict[str, Any]], int]:
    """Build anomaly records and count unmatched messages."""

    records: list[dict[str, Any]] = []
    messages_not_found = 0

    for row in dataframe.to_dict(orient="records"):
        identity = _identity_key(
            row["mmsi"],
            row["timestamp"],
            row["latitude"],
            row["longitude"],
        )

        link = message_links.get(identity)

        if link is None:
            messages_not_found += 1
            continue

        message_id, vessel_id = link

        timestamp = row["timestamp"]

        if isinstance(timestamp, pd.Timestamp):
            observed_at = timestamp.to_pydatetime()
        else:
            observed_at = timestamp

        records.append(
            {
                "ais_message_id": message_id,
                "vessel_id": vessel_id,
                "observed_at": observed_at,
                "anomaly_type": str(row["anomaly_type"]),
                "severity": str(row["severity"]),
                "metric_name": str(row["metric_name"]),
                "metric_value": _optional_float(row.get("metric_value")),
                "threshold": _optional_float(row.get("threshold")),
                "message": str(row["message"]),
            }
        )

    return records, messages_not_found


def _batches(
    records: list[dict[str, Any]],
    batch_size: int,
) -> Iterator[list[dict[str, Any]]]:
    """Yield fixed-size insertion batches."""

    for start in range(
        0,
        len(records),
        batch_size,
    ):
        yield records[start : start + batch_size]


def _insert_alerts(
    session: Session,
    records: list[dict[str, Any]],
) -> int:
    """Insert alerts and return the inserted count."""

    if not records:
        return 0

    statement = (
        insert(AnomalyAlert)
        .values(records)
        .on_conflict_do_nothing(constraint="message_anomaly_type")
        .returning(AnomalyAlert.id)
    )

    inserted_ids = session.execute(statement).scalars().all()

    return len(inserted_ids)


def import_anomaly_alerts_csv(
    session: Session,
    source_file: Path,
    *,
    chunk_size: int = 5_000,
    insert_batch_size: int = 1_000,
    maximum_rows: int | None = None,
) -> AlertImportSummary:
    """Import anomaly alerts and link them to AIS messages."""

    source_file = source_file.resolve()

    if not source_file.exists():
        raise FileNotFoundError(f"Alert CSV does not exist: {source_file}")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    if insert_batch_size <= 0:
        raise ValueError("insert_batch_size must be positive.")

    rows_read = 0
    rows_imported = 0
    rows_rejected = 0
    messages_not_found = 0
    duplicates_skipped = 0

    csv_chunks = pd.read_csv(
        source_file,
        chunksize=chunk_size,
        nrows=maximum_rows,
        low_memory=False,
        dtype={"mmsi": "string"},
    )

    try:
        for source_chunk in csv_chunks:
            rows_read += len(source_chunk)

            prepared, rejected_count = _prepare_alert_chunk(source_chunk)

            rows_rejected += rejected_count

            message_links = _load_message_links(
                session,
                prepared,
            )

            records, unmatched_count = _build_alert_records(
                prepared,
                message_links,
            )

            messages_not_found += unmatched_count

            for batch in _batches(
                records,
                insert_batch_size,
            ):
                inserted_count = _insert_alerts(
                    session,
                    batch,
                )

                rows_imported += inserted_count

                duplicates_skipped += len(batch) - inserted_count

            session.commit()

    except Exception:
        session.rollback()
        raise

    return AlertImportSummary(
        source_file=str(source_file),
        rows_read=rows_read,
        rows_imported=rows_imported,
        rows_rejected=rows_rejected,
        messages_not_found=messages_not_found,
        duplicates_skipped=duplicates_skipped,
    )
