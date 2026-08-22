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

from seaguard.db.models import AISMessage, Vessel
from seaguard.db.risk_models import RiskAssessment

REQUIRED_RISK_IMPORT_COLUMNS = {
    "mmsi",
    "timestamp",
    "ml_anomaly_score",
    "ml_anomaly_percentile",
    "rule_flag_count",
    "rule_severity",
    "detector_agreement",
    "risk_level",
    "risk_reasons",
}

VALID_RULE_SEVERITIES = {"none", "warning", "high", "critical"}
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

DEFAULT_ASSESSMENT_VERSION = "hybrid-v1"


@dataclass(frozen=True, slots=True)
class RiskImportSummary:
    """Results from one hybrid-risk CSV import."""

    source_file: str
    rows_read: int
    rows_imported: int
    rows_rejected: int
    messages_not_found: int


def _is_missing(value: Any) -> bool:
    """Return whether a scalar value is missing."""

    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _optional_text(value: Any) -> str | None:
    """Convert a value to stripped text or None."""

    if _is_missing(value):
        return None

    text = str(value).strip()
    return text or None


def _optional_bool(value: Any) -> bool:
    """Convert common CSV Boolean values to bool."""

    if _is_missing(value):
        return False

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"true", "1", "yes"}


def _prepare_risk_chunk(
    source: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """
    Validate and normalize one hybrid-risk CSV chunk.

    Returns the usable rows and the number of rejected rows.
    """

    missing_columns = REQUIRED_RISK_IMPORT_COLUMNS - set(source.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"Missing required risk import columns: {missing}",
        )

    dataframe = source.copy()

    dataframe["mmsi"] = (
        dataframe["mmsi"]
        .astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
        utc=True,
    )

    for column in [
        "ml_anomaly_score",
        "ml_anomaly_percentile",
        "rule_flag_count",
    ]:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe["rule_severity"] = (
        dataframe["rule_severity"].astype("string").str.strip().str.lower()
    )

    dataframe["risk_level"] = (
        dataframe["risk_level"].astype("string").str.strip().str.lower()
    )

    dataframe["detector_agreement"] = (
        dataframe["detector_agreement"].map(_optional_bool).astype(bool)
    )

    dataframe["risk_reasons"] = dataframe["risk_reasons"].astype("string").str.strip()

    valid_rows = (
        dataframe["mmsi"].str.fullmatch(r"\d{9}", na=False)
        & dataframe["timestamp"].notna()
        & dataframe["ml_anomaly_score"].notna()
        & dataframe["ml_anomaly_percentile"].between(0.0, 100.0)
        & dataframe["rule_flag_count"].notna()
        & dataframe["rule_flag_count"].ge(0.0)
        & dataframe["rule_severity"].isin(VALID_RULE_SEVERITIES)
        & dataframe["risk_level"].isin(VALID_RISK_LEVELS)
        & dataframe["risk_reasons"].notna()
        & dataframe["risk_reasons"].ne("")
    )

    rejected_count = int((~valid_rows).sum())

    prepared = dataframe.loc[valid_rows].copy().reset_index(drop=True)

    prepared["rule_flag_count"] = prepared["rule_flag_count"].astype(int)

    return prepared, rejected_count


def _vessel_ids_for_chunk(
    session: Session,
    dataframe: pd.DataFrame,
) -> dict[str, int]:
    """Resolve MMSI values to vessel primary keys."""

    mmsi_values = dataframe["mmsi"].dropna().astype(str).unique().tolist()

    if not mmsi_values:
        return {}

    rows = session.execute(
        select(Vessel.id, Vessel.mmsi).where(
            Vessel.mmsi.in_(mmsi_values),
        )
    ).all()

    return {str(mmsi): int(vessel_id) for vessel_id, mmsi in rows}


def _message_ids_for_chunk(
    session: Session,
    dataframe: pd.DataFrame,
    vessel_ids: dict[str, int],
) -> dict[tuple[int, datetime], int]:
    """Resolve vessel/timestamp pairs to AIS message primary keys."""

    lookup_pairs: list[tuple[int, datetime]] = []

    for row in dataframe.itertuples(index=False):
        vessel_id = vessel_ids.get(str(row.mmsi))

        if vessel_id is None:
            continue

        timestamp = row.timestamp

        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()

        lookup_pairs.append((vessel_id, timestamp))

    if not lookup_pairs:
        return {}

    unique_pairs = list(dict.fromkeys(lookup_pairs))

    rows = session.execute(
        select(
            AISMessage.id,
            AISMessage.vessel_id,
            AISMessage.timestamp,
        ).where(
            tuple_(
                AISMessage.vessel_id,
                AISMessage.timestamp,
            ).in_(unique_pairs)
        )
    ).all()

    return {
        (int(vessel_id), timestamp): int(message_id)
        for message_id, vessel_id, timestamp in rows
    }


def _build_risk_records(
    dataframe: pd.DataFrame,
    vessel_ids: dict[str, int],
    message_ids: dict[tuple[int, datetime], int],
    *,
    assessment_version: str,
) -> tuple[list[dict[str, Any]], int]:
    """
    Build database records for rows that match an AIS message.

    Returns the records and the number of rows whose AIS message
    could not be resolved.
    """

    records: list[dict[str, Any]] = []
    messages_not_found = 0

    for row in dataframe.itertuples(index=False):
        mmsi = str(row.mmsi)
        vessel_id = vessel_ids.get(mmsi)

        if vessel_id is None:
            messages_not_found += 1
            continue

        observed_at = row.timestamp

        if isinstance(observed_at, pd.Timestamp):
            observed_at = observed_at.to_pydatetime()

        ais_message_id = message_ids.get(
            (vessel_id, observed_at),
        )

        if ais_message_id is None:
            messages_not_found += 1
            continue

        records.append(
            {
                "ais_message_id": ais_message_id,
                "vessel_id": vessel_id,
                "observed_at": observed_at,
                "ml_anomaly_score": float(row.ml_anomaly_score),
                "ml_anomaly_percentile": float(
                    row.ml_anomaly_percentile,
                ),
                "rule_flag_count": int(row.rule_flag_count),
                "rule_severity": str(row.rule_severity),
                "detector_agreement": bool(
                    row.detector_agreement,
                ),
                "risk_level": str(row.risk_level),
                "risk_reasons": (
                    _optional_text(row.risk_reasons) or "no_elevated_evidence"
                ),
                "assessment_version": assessment_version,
            }
        )

    return records, messages_not_found


def _batched_records(
    records: list[dict[str, Any]],
    batch_size: int,
) -> Iterator[list[dict[str, Any]]]:
    """Yield consecutive record batches."""

    if batch_size <= 0:
        raise ValueError(
            "insert_batch_size must be greater than zero.",
        )

    for start in range(0, len(records), batch_size):
        yield records[start : start + batch_size]


def _upsert_risk_records(
    session: Session,
    records: list[dict[str, Any]],
    *,
    batch_size: int,
) -> int:
    """Insert or update hybrid risk assessments."""

    imported = 0

    for batch in _batched_records(records, batch_size):
        statement = insert(RiskAssessment).values(batch)
        excluded = statement.excluded

        statement = statement.on_conflict_do_update(
            index_elements=[
                RiskAssessment.ais_message_id,
            ],
            set_={
                "vessel_id": excluded.vessel_id,
                "observed_at": excluded.observed_at,
                "ml_anomaly_score": excluded.ml_anomaly_score,
                "ml_anomaly_percentile": (excluded.ml_anomaly_percentile),
                "rule_flag_count": excluded.rule_flag_count,
                "rule_severity": excluded.rule_severity,
                "detector_agreement": (excluded.detector_agreement),
                "risk_level": excluded.risk_level,
                "risk_reasons": excluded.risk_reasons,
                "assessment_version": (excluded.assessment_version),
            },
        )

        session.execute(statement)
        imported += len(batch)

    return imported


def import_risk_assessments_csv(
    session: Session,
    file_path: Path,
    *,
    chunk_size: int = 5_000,
    insert_batch_size: int = 1_000,
    maximum_rows: int | None = None,
    assessment_version: str = DEFAULT_ASSESSMENT_VERSION,
) -> RiskImportSummary:
    """
    Import hybrid risk assessments from CSV.

    Each assessment is matched to an existing AISMessage by
    MMSI + timestamp. Existing assessments are updated using
    the unique ais_message_id constraint, making the import
    idempotent.
    """

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than zero.",
        )

    if insert_batch_size <= 0:
        raise ValueError(
            "insert_batch_size must be greater than zero.",
        )

    if maximum_rows is not None and maximum_rows <= 0:
        raise ValueError(
            "maximum_rows must be greater than zero.",
        )

    if not file_path.exists():
        raise FileNotFoundError(
            f"Risk CSV does not exist: {file_path}",
        )

    rows_read = 0
    rows_imported = 0
    rows_rejected = 0
    messages_not_found = 0

    reader = pd.read_csv(
        file_path,
        chunksize=chunk_size,
        nrows=maximum_rows,
    )

    try:
        for chunk in reader:
            rows_read += len(chunk)

            prepared, rejected = _prepare_risk_chunk(chunk)
            rows_rejected += rejected

            if prepared.empty:
                continue

            vessel_ids = _vessel_ids_for_chunk(
                session,
                prepared,
            )

            message_ids = _message_ids_for_chunk(
                session,
                prepared,
                vessel_ids,
            )

            records, missing = _build_risk_records(
                prepared,
                vessel_ids,
                message_ids,
                assessment_version=assessment_version,
            )

            messages_not_found += missing

            rows_imported += _upsert_risk_records(
                session,
                records,
                batch_size=insert_batch_size,
            )

        session.commit()

    except Exception:
        session.rollback()
        raise

    return RiskImportSummary(
        source_file=str(file_path),
        rows_read=rows_read,
        rows_imported=rows_imported,
        rows_rejected=rows_rejected,
        messages_not_found=messages_not_found,
    )
