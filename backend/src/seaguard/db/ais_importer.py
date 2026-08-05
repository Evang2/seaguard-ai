from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from seaguard.db.models import AISMessage, ImportJob, Vessel

REQUIRED_IMPORT_COLUMNS = {
    "mmsi",
    "timestamp",
    "latitude",
    "longitude",
}

NUMERIC_IMPORT_COLUMNS = [
    "sog",
    "cog",
    "heading",
    "navigation_status",
    "cargo",
    "vessel_type",
    "length_m",
    "width_m",
    "draft_m",
]


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """Results from one AIS CSV import."""

    job_id: int
    source_file: str
    rows_read: int
    rows_imported: int
    rows_rejected: int
    duplicates_skipped: int


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


def _optional_float(value: Any) -> float | None:
    """Convert a value to float or None."""

    if _is_missing(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    """Convert a numeric-like value to int or None."""

    if _is_missing(value):
        return None

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool:
    """Convert common CSV Boolean values to bool."""

    if _is_missing(value):
        return False

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
    }


def _last_present_value(
    dataframe: pd.DataFrame,
    column: str,
) -> Any:
    """Return the last nonmissing value from a column."""

    if column not in dataframe.columns:
        return None

    values = dataframe[column].dropna()

    if values.empty:
        return None

    return values.iloc[-1]


def _prepare_import_chunk(
    source: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """
    Validate and normalize one CSV chunk.

    Returns the usable rows and the number of rejected rows.
    """

    missing_columns = REQUIRED_IMPORT_COLUMNS - set(source.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))

        raise ValueError(f"Missing required AIS import columns: {missing}")

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

    dataframe["latitude"] = pd.to_numeric(
        dataframe["latitude"],
        errors="coerce",
    )

    dataframe["longitude"] = pd.to_numeric(
        dataframe["longitude"],
        errors="coerce",
    )

    for column in NUMERIC_IMPORT_COLUMNS:
        if column in dataframe.columns:
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
    )

    rejected_count = int((~valid_rows).sum())

    prepared = dataframe.loc[valid_rows].reset_index(drop=True)

    return prepared, rejected_count


def _build_vessel_records(
    dataframe: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Aggregate vessel metadata from one AIS chunk."""

    records: list[dict[str, Any]] = []

    for mmsi, vessel_rows in dataframe.groupby(
        "mmsi",
        sort=False,
        dropna=True,
    ):
        first_seen = vessel_rows["timestamp"].min()
        last_seen = vessel_rows["timestamp"].max()

        records.append(
            {
                "mmsi": str(mmsi),
                "imo": _optional_text(
                    _last_present_value(
                        vessel_rows,
                        "imo",
                    )
                ),
                "name": _optional_text(
                    _last_present_value(
                        vessel_rows,
                        "vessel_name",
                    )
                ),
                "call_sign": _optional_text(
                    _last_present_value(
                        vessel_rows,
                        "call_sign",
                    )
                ),
                "vessel_type": _optional_int(
                    _last_present_value(
                        vessel_rows,
                        "vessel_type",
                    )
                ),
                "length_m": _optional_float(
                    _last_present_value(
                        vessel_rows,
                        "length_m",
                    )
                ),
                "width_m": _optional_float(
                    _last_present_value(
                        vessel_rows,
                        "width_m",
                    )
                ),
                "draft_m": _optional_float(
                    _last_present_value(
                        vessel_rows,
                        "draft_m",
                    )
                ),
                "first_seen": first_seen.to_pydatetime(),
                "last_seen": last_seen.to_pydatetime(),
            }
        )

    return records


def _upsert_vessels(
    session: Session,
    records: list[dict[str, Any]],
) -> None:
    """Create vessels or update their latest known metadata."""

    if not records:
        return

    statement = insert(Vessel).values(records)
    excluded = statement.excluded

    statement = statement.on_conflict_do_update(
        index_elements=[Vessel.mmsi],
        set_={
            "imo": func.coalesce(
                excluded.imo,
                Vessel.imo,
            ),
            "name": func.coalesce(
                excluded.name,
                Vessel.name,
            ),
            "call_sign": func.coalesce(
                excluded.call_sign,
                Vessel.call_sign,
            ),
            "vessel_type": func.coalesce(
                excluded.vessel_type,
                Vessel.vessel_type,
            ),
            "length_m": func.coalesce(
                excluded.length_m,
                Vessel.length_m,
            ),
            "width_m": func.coalesce(
                excluded.width_m,
                Vessel.width_m,
            ),
            "draft_m": func.coalesce(
                excluded.draft_m,
                Vessel.draft_m,
            ),
            "first_seen": func.least(
                func.coalesce(
                    Vessel.first_seen,
                    excluded.first_seen,
                ),
                func.coalesce(
                    excluded.first_seen,
                    Vessel.first_seen,
                ),
            ),
            "last_seen": func.greatest(
                func.coalesce(
                    Vessel.last_seen,
                    excluded.last_seen,
                ),
                func.coalesce(
                    excluded.last_seen,
                    Vessel.last_seen,
                ),
            ),
        },
    )

    session.execute(statement)


def _load_vessel_ids(
    session: Session,
    mmsis: list[str],
) -> dict[str, int]:
    """Return database vessel IDs keyed by MMSI."""

    if not mmsis:
        return {}

    result = session.execute(
        select(
            Vessel.mmsi,
            Vessel.id,
        ).where(Vessel.mmsi.in_(mmsis))
    )

    return {mmsi: vessel_id for mmsi, vessel_id in result.all()}


def _build_message_records(
    dataframe: pd.DataFrame,
    vessel_ids: dict[str, int],
) -> list[dict[str, Any]]:
    """Convert prepared DataFrame rows to database records."""

    records: list[dict[str, Any]] = []

    for row in dataframe.to_dict(orient="records"):
        mmsi = str(row["mmsi"])
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])

        records.append(
            {
                "vessel_id": vessel_ids[mmsi],
                "timestamp": row["timestamp"].to_pydatetime(),
                "latitude": latitude,
                "longitude": longitude,
                "position": WKTElement(
                    f"POINT({longitude} {latitude})",
                    srid=4326,
                ),
                "sog": _optional_float(row.get("sog")),
                "cog": _optional_float(row.get("cog")),
                "heading": _optional_float(row.get("heading")),
                "navigation_status": _optional_int(row.get("navigation_status")),
                "cargo": _optional_int(row.get("cargo")),
                "transceiver_class": _optional_text(row.get("transceiver_class")),
                "sog_unavailable": _optional_bool(row.get("sog_unavailable")),
                "cog_unavailable": _optional_bool(row.get("cog_unavailable")),
                "heading_unavailable": _optional_bool(row.get("heading_unavailable")),
            }
        )

    return records


def _batches(
    records: list[dict[str, Any]],
    batch_size: int,
) -> Iterator[list[dict[str, Any]]]:
    """Yield fixed-size insertion batches."""

    for start in range(0, len(records), batch_size):
        yield records[start : start + batch_size]


def _insert_messages(
    session: Session,
    records: list[dict[str, Any]],
) -> int:
    """Insert AIS messages and return the inserted count."""

    if not records:
        return 0

    statement = (
        insert(AISMessage)
        .values(records)
        .on_conflict_do_nothing(constraint="identity")
        .returning(AISMessage.id)
    )

    inserted_ids = session.execute(statement).scalars().all()

    return len(inserted_ids)


def import_clean_ais_csv(
    session: Session,
    source_file: Path,
    *,
    chunk_size: int = 5_000,
    insert_batch_size: int = 1_000,
    maximum_rows: int | None = None,
) -> ImportSummary:
    """Import a cleaned AIS CSV into the SeaGuard database."""

    source_file = source_file.resolve()

    if not source_file.exists():
        raise FileNotFoundError(f"AIS CSV does not exist: {source_file}")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    if insert_batch_size <= 0:
        raise ValueError("insert_batch_size must be positive.")

    import_job = ImportJob(
        source_file=str(source_file),
        status="running",
    )

    session.add(import_job)
    session.commit()
    session.refresh(import_job)

    job_id = import_job.id

    rows_read = 0
    rows_imported = 0
    rows_rejected = 0
    duplicates_skipped = 0

    try:
        csv_chunks = pd.read_csv(
            source_file,
            chunksize=chunk_size,
            nrows=maximum_rows,
            low_memory=False,
            dtype={"mmsi": "string"},
        )

        for source_chunk in csv_chunks:
            rows_read += len(source_chunk)

            prepared, rejected_count = _prepare_import_chunk(source_chunk)

            rows_rejected += rejected_count

            if not prepared.empty:
                vessel_records = _build_vessel_records(prepared)

                _upsert_vessels(
                    session,
                    vessel_records,
                )

                mmsis = prepared["mmsi"].dropna().astype(str).unique().tolist()

                vessel_ids = _load_vessel_ids(
                    session,
                    mmsis,
                )

                message_records = _build_message_records(
                    prepared,
                    vessel_ids,
                )

                for batch in _batches(
                    message_records,
                    insert_batch_size,
                ):
                    inserted_count = _insert_messages(
                        session,
                        batch,
                    )

                    rows_imported += inserted_count
                    duplicates_skipped += len(batch) - inserted_count

            import_job.rows_read = rows_read
            import_job.rows_imported = rows_imported
            import_job.rows_rejected = rows_rejected
            import_job.duplicates_skipped = duplicates_skipped

            session.commit()

        import_job.status = "completed"
        import_job.finished_at = datetime.now(UTC)
        session.commit()

    except Exception as error:
        session.rollback()

        failed_job = session.get(
            ImportJob,
            job_id,
        )

        if failed_job is not None:
            failed_job.status = "failed"
            failed_job.rows_read = rows_read
            failed_job.rows_imported = rows_imported
            failed_job.rows_rejected = rows_rejected
            failed_job.duplicates_skipped = duplicates_skipped
            failed_job.error_message = str(error)[:4000]
            failed_job.finished_at = datetime.now(UTC)

            session.commit()

        raise

    return ImportSummary(
        job_id=job_id,
        source_file=str(source_file),
        rows_read=rows_read,
        rows_imported=rows_imported,
        rows_rejected=rows_rejected,
        duplicates_skipped=duplicates_skipped,
    )
